import re

from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from analytics.models import AuditLog
from incidents.models import Incident
from incidents.serializers import IncidentSerializer
from .legal import TERMS_VERSION
from .sockets import disconnect_user

PHONE_RE = re.compile(r'^\+?[0-9 ()\-]{7,20}$')
REPORTER_FIELDS = ('reporter', 'reported_by', 'created_by', 'user')
FINISHED = ('resolved', 'closed')


def _mine(user):
  """Incidents this user reported."""
  for name in REPORTER_FIELDS:
    try:
      Incident._meta.get_field(name)
    except FieldDoesNotExist:
      continue
    return Incident.objects.filter(**{name: user})
  raise ImproperlyConfigured(
    'Incident has no reporter field called one of: ' + ', '.join(REPORTER_FIELDS)
  )


def _profile(user):
  return {
    'full_name': user.full_name,
    'email': user.email,
    'phone_number': user.phone_number,
    'role': user.role,
    'created_at': user.created_at,
    'accepted_terms_version': user.accepted_terms_version,
    'accepted_terms_at': user.accepted_terms_at,
  }


class ProfileView(APIView):
  permission_classes = [permissions.IsAuthenticated]

  def get(self, request):
    return Response(_profile(request.user))

  def patch(self, request):
    user = request.user
    errors = {}
    if 'full_name' in request.data:
      name = str(request.data['full_name']).strip()
      if not 2 <= len(name) <= 150:
        errors['full_name'] = 'Enter your full name (2 to 150 characters).'
      else:
        user.full_name = name
    if 'phone_number' in request.data:
      phone = str(request.data['phone_number']).strip()
      if phone and not PHONE_RE.match(phone):
        errors['phone_number'] = 'Enter a valid phone number, e.g. +254 700 000 000.'
      else:
        user.phone_number = phone
    if errors:
      raise serializers.ValidationError(errors)
    user.save(update_fields=['full_name', 'phone_number'])
    return Response(_profile(user))


class ExportDataView(APIView):
  """Everything we hold about the signed-in user, as a JSON download."""
  permission_classes = [permissions.IsAuthenticated]

  def get(self, request):
    user = request.user
    incidents = IncidentSerializer(_mine(user), many=True, context={'request': request}).data
    response = Response({
      'exported_at': timezone.now().isoformat(),
      'profile': _profile(user),
      'incidents_reported': incidents,
    })
    response['Content-Disposition'] = 'attachment; filename="serims-my-data.json"'
    return response


class AcceptTermsView(APIView):
  permission_classes = [permissions.IsAuthenticated]

  def post(self, request):
    user = request.user
    user.accepted_terms_version = TERMS_VERSION
    user.accepted_terms_at = timezone.now()
    user.save(update_fields=['accepted_terms_version', 'accepted_terms_at'])
    return Response({'detail': 'Terms accepted.', 'version': TERMS_VERSION})


class DeleteThrottle(UserRateThrottle):
  scope = 'account_delete'
  rate = '5/hour'


class DeleteAccountView(APIView):
  permission_classes = [permissions.IsAuthenticated]
  throttle_classes = [DeleteThrottle]

  @transaction.atomic
  def post(self, request):
    user = request.user
    if user.role != 'general_user':
      raise PermissionDenied(
        'Staff and administrator accounts are managed by an administrator. Ask them to deactivate yours.'
      )
    if not user.check_password(str(request.data.get('password', ''))):
      raise serializers.ValidationError({'password': 'Your password is incorrect.'})
    if str(request.data.get('confirm', '')).strip() != 'DELETE':
      raise serializers.ValidationError({'confirm': 'Type DELETE to confirm.'})
    open_count = _mine(user).exclude(status__in=FINISHED).count()
    if open_count:
      raise serializers.ValidationError({
        'detail': f'You have {open_count} incident(s) still being handled. '
                  'You can delete your account once they are resolved.'
      })

    AuditLog.objects.create(user=user, action='Deleted own account', entity_affected='Account')

    # Anonymise in place: reports stay for the response teams' records, but no
    # longer identify anyone. Changing the password hash also revokes every token.
    user.full_name = 'Deleted user'
    user.email = f'deleted-{user.pk}@deleted.invalid'
    user.phone_number = ''
    user.is_active = False
    user.must_change_password = False
    user.set_unusable_password()
    user.save()
    transaction.on_commit(lambda: disconnect_user(user))
    return Response({'detail': 'Your account has been deleted.'})
