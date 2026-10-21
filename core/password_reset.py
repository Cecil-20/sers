from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from notifications.account_mail import send_reset_link
from users.models import User
from .sockets import disconnect_user


class ForgotThrottle(AnonRateThrottle):
  scope = 'forgot_password'
  rate = '10/hour'


class ConfirmThrottle(AnonRateThrottle):
  scope = 'reset_password'
  rate = '20/hour'


class ForgotPasswordView(APIView):
  # No authentication: a stale token in the browser must not block this call.
  authentication_classes = []
  permission_classes = [permissions.AllowAny]
  throttle_classes = [ForgotThrottle]

  def post(self, request):
    email = str(request.data.get('email', '')).strip().lower()
    user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None
    if user:
      send_reset_link(user)
    # Same answer whether or not the account exists, so emails cannot be probed.
    return Response({'detail': 'If an account exists for that email, a reset link has been sent.'})


class ResetPasswordConfirmView(APIView):
  authentication_classes = []
  permission_classes = [permissions.AllowAny]
  throttle_classes = [ConfirmThrottle]

  def post(self, request):
    invalid = serializers.ValidationError(
      {'detail': 'This link is invalid or has expired. Request a new one.'}
    )
    try:
      pk = force_str(urlsafe_base64_decode(str(request.data.get('uid', ''))))
      user = User.objects.get(pk=pk, is_active=True)
    except (ValueError, TypeError, OverflowError, User.DoesNotExist, DjangoValidationError):
      raise invalid
    if not default_token_generator.check_token(user, str(request.data.get('token', ''))):
      raise invalid

    new = str(request.data.get('new_password', ''))
    try:
      validate_password(new, user=user)
    except DjangoValidationError as exc:
      raise serializers.ValidationError({'new_password': list(exc.messages)})

    # Saving a new password also kills the link (the token is tied to the old
    # hash) and every session issued before now.
    user.set_password(new)
    user.must_change_password = False
    user.save(update_fields=['password', 'must_change_password'])
    disconnect_user(user)
    return Response({'detail': 'Password set. You can sign in now.'})
