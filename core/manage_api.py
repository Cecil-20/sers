import re
import uuid

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from incidents.models import Incident
from teams.models import EmergencyCategory, ResponseTeam, TeamMember
from users.models import User
from .permissions import IsGeneralAdmin
from .sockets import disconnect_user

GUARDS = [permissions.IsAuthenticated, IsGeneralAdmin]
PHONE_RE = re.compile(r'^\+?[0-9 ()\-]{7,20}$')
STAFF_ROLES = ('team_leader', 'team_member')
CREATABLE_ROLES = ('team_leader', 'team_member', 'general_admin')


# ---- helpers ---------------------------------------------------------------

def _open_incidents(team):
  return Incident.objects.filter(team=team).exclude(status='closed').count()


def _current_team(user):
  membership = next(iter(user.team_memberships.all()), None)
  return membership.team if membership else None


def _fresh_user(pk):
  return User.objects.prefetch_related('team_memberships__team').get(pk=pk)


def _sync_membership(user, team):
  """A staff user belongs to exactly one team; everyone else to none."""
  memberships = user.team_memberships.all()
  if team is None:
    memberships.delete()
    return
  memberships.exclude(team=team).delete()
  TeamMember.objects.get_or_create(team=team, user=user)
  if user.role == 'team_leader' and team.leader_id is None:
    team.leader = user
    team.save(update_fields=['leader'])


def _check_password(password, email, full_name):
  candidate = User(email=email or '', full_name=full_name or '')
  try:
    validate_password(password, user=candidate)
  except DjangoValidationError as exc:
    raise serializers.ValidationError({'password': list(exc.messages)})


# ---- teams -----------------------------------------------------------------

class TeamAdminSerializer(serializers.ModelSerializer):
  leader_name = serializers.SerializerMethodField()
  member_count = serializers.SerializerMethodField()
  category_count = serializers.SerializerMethodField()
  open_incidents = serializers.SerializerMethodField()

  class Meta:
    model = ResponseTeam
    fields = [
      'id', 'team_name', 'hotline_number', 'team_email', 'is_active',
      'leader', 'leader_name', 'member_count', 'category_count',
      'open_incidents', 'created_at',
    ]
    read_only_fields = ['id', 'created_at']
    extra_kwargs = {'leader': {'required': False, 'allow_null': True}}

  def get_leader_name(self, obj):
    return obj.leader.full_name if obj.leader else None

  def get_member_count(self, obj):
    return obj.members.count()

  def get_category_count(self, obj):
    return obj.categories.count()

  def get_open_incidents(self, obj):
    return _open_incidents(obj)

  def validate_team_name(self, value):
    value = value.strip()
    taken = ResponseTeam.objects.filter(team_name__iexact=value)
    if self.instance:
      taken = taken.exclude(pk=self.instance.pk)
    if taken.exists():
      raise serializers.ValidationError('A team with this name already exists.')
    return value

  def validate_hotline_number(self, value):
    if not PHONE_RE.match(value.strip()):
      raise serializers.ValidationError('Enter a valid phone number, e.g. +254 700 000 000.')
    return value.strip()

  def validate_leader(self, value):
    if value is None:
      return value
    if self.instance is None:
      raise serializers.ValidationError(
        'Create the team first, then create a team-leader account for it.'
      )
    if value.role != 'team_leader' or not value.is_active:
      raise serializers.ValidationError('The leader must be an active team-leader account.')
    if not TeamMember.objects.filter(team=self.instance, user=value).exists():
      raise serializers.ValidationError('The leader must belong to this team.')
    return value

  def validate(self, attrs):
    inst = self.instance
    if inst and inst.is_active and attrs.get('is_active') is False:
      open_count = _open_incidents(inst)
      if open_count:
        raise serializers.ValidationError({
          'is_active': f'This team has {open_count} open incident(s). '
                       'Close them before deactivating the team.'
        })
    return attrs


class TeamAdminViewSet(viewsets.ModelViewSet):
  serializer_class = TeamAdminSerializer
  permission_classes = GUARDS
  http_method_names = ['get', 'post', 'patch', 'head', 'options']
  queryset = ResponseTeam.objects.select_related('leader').order_by('team_name')


# ---- categories --------------------------------------------------------------

class CategoryAdminSerializer(serializers.ModelSerializer):
  team_name = serializers.CharField(source='team.team_name', read_only=True)
  incident_count = serializers.SerializerMethodField()

  class Meta:
    model = EmergencyCategory
    fields = ['id', 'category_name', 'team', 'team_name', 'is_custom', 'incident_count']
    read_only_fields = ['id']

  def get_incident_count(self, obj):
    return Incident.objects.filter(category=obj).count()

  def validate_category_name(self, value):
    value = value.strip()
    taken = EmergencyCategory.objects.filter(category_name__iexact=value)
    if self.instance:
      taken = taken.exclude(pk=self.instance.pk)
    if taken.exists():
      raise serializers.ValidationError('A category with this name already exists.')
    return value

  def validate_team(self, value):
    changed = self.instance is None or self.instance.team_id != value.id
    if changed and not value.is_active:
      raise serializers.ValidationError('That team is deactivated.')
    return value


class CategoryAdminViewSet(viewsets.ModelViewSet):
  serializer_class = CategoryAdminSerializer
  permission_classes = GUARDS
  http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
  queryset = EmergencyCategory.objects.select_related('team').order_by('category_name')

  def perform_destroy(self, instance):
    used = Incident.objects.filter(category=instance).count()
    if used:
      raise serializers.ValidationError({
        'detail': f'{used} incident(s) use this category, so it cannot be deleted. '
                  'Rename it or move it to another team instead.'
      })
    instance.delete()


# ---- accounts ----------------------------------------------------------------

def _check_protections(inst, actor, role, active, team):
  if inst.pk == actor.pk and (role != inst.role or not active):
    raise serializers.ValidationError({
      'detail': 'You cannot change your own role or deactivate your own account.'
    })
  if inst.role == 'general_admin' and inst.is_active and (role != 'general_admin' or not active):
    others = User.objects.filter(role='general_admin', is_active=True).exclude(pk=inst.pk)
    if not others.exists():
      raise serializers.ValidationError({
        'detail': 'This is the last active administrator, so it cannot be changed or deactivated.'
      })
  led = list(ResponseTeam.objects.filter(leader=inst))
  if led:
    leaving = role != 'team_leader' or not active or team is None
    moving = team is not None and any(t.pk != team.pk for t in led)
    if leaving or moving:
      names = ', '.join(t.team_name for t in led)
      raise serializers.ValidationError({
        'detail': f'{inst.full_name} is the leader of {names}. '
                  'Choose another leader for that team first.'
      })


class AccountAdminSerializer(serializers.ModelSerializer):
  password = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'})
  team = serializers.PrimaryKeyRelatedField(
    queryset=ResponseTeam.objects.all(), required=False, allow_null=True, write_only=True
  )
  team_id = serializers.SerializerMethodField()
  team_name = serializers.SerializerMethodField()
  invite_sent = serializers.SerializerMethodField()

  class Meta:
    model = User
    fields = [
      'id', 'full_name', 'email', 'phone_number', 'role', 'is_active',
      'team', 'team_id', 'team_name', 'password', 'created_at',
      'must_change_password', 'invite_sent',
    ]
    read_only_fields = ['id', 'created_at', 'must_change_password']

  def get_team_id(self, obj):
    team = _current_team(obj)
    return str(team.pk) if team else None

  def get_team_name(self, obj):
    team = _current_team(obj)
    return team.team_name if team else None

  def get_invite_sent(self, obj):
    return getattr(obj, '_invite_sent', None)

  def validate_email(self, value):
    value = value.strip().lower()
    taken = User.objects.filter(email__iexact=value)
    if self.instance:
      taken = taken.exclude(pk=self.instance.pk)
    if taken.exists():
      raise serializers.ValidationError('An account with this email already exists.')
    return value

  def validate(self, attrs):
    inst = self.instance
    actor = self.context['request'].user
    role = attrs.get('role', inst.role if inst else None)
    active = attrs.get('is_active', inst.is_active if inst else True)
    if 'team' in attrs:
      team = attrs['team']
    else:
      team = _current_team(inst) if inst else None

    if inst is None:
      if role not in CREATABLE_ROLES:
        raise serializers.ValidationError(
          {'role': 'Choose team leader, team member or administrator.'}
        )
    elif 'password' in attrs:
      raise serializers.ValidationError({'password': 'Use "Reset password" to change a password.'})

    if role in STAFF_ROLES:
      if team is None:
        raise serializers.ValidationError({'team': 'Choose the team this person belongs to.'})
      if not team.is_active and (inst is None or _current_team(inst) != team):
        raise serializers.ValidationError({'team': 'That team is deactivated.'})
    else:
      team = None
    attrs['team'] = team

    if attrs.get('password'):
      _check_password(attrs['password'], attrs.get('email'), attrs.get('full_name'))
    if inst is not None:
      _check_protections(inst, actor, role, active, team)
    return attrs

  @transaction.atomic
  def create(self, validated_data):
    from notifications.account_mail import send_reset_link
    password = validated_data.pop('password', None)
    team = validated_data.pop('team', None)
    user = User.objects.create_user(
      password=password, must_change_password=bool(password), **validated_data
    )
    _sync_membership(user, team)
    fresh = _fresh_user(user.pk)
    fresh._invite_sent = None
    if not password:
      fresh._invite_sent = send_reset_link(fresh, invite=True)
    return fresh

  @transaction.atomic
  def update(self, instance, validated_data):
    team = validated_data.pop('team', None)
    before = (instance.role, instance.is_active, _current_team(instance))
    for field, value in validated_data.items():
      setattr(instance, field, value)
    instance.save()
    _sync_membership(instance, team)
    if (instance.role, instance.is_active, team) != before:
      # Open alert sockets still carry the old team and role. End them so they
      # reconnect with the right groups, or not at all if deactivated.
      transaction.on_commit(lambda: disconnect_user(instance))
    return _fresh_user(instance.pk)


class AccountAdminViewSet(viewsets.ModelViewSet):
  serializer_class = AccountAdminSerializer
  permission_classes = GUARDS
  http_method_names = ['get', 'post', 'patch', 'head', 'options']

  def get_queryset(self):
    qs = User.objects.prefetch_related('team_memberships__team').order_by('full_name')
    params = self.request.query_params
    search = params.get('search', '').strip()
    if search:
      qs = qs.filter(Q(full_name__icontains=search) | Q(email__icontains=search))
    if params.get('role'):
      qs = qs.filter(role=params['role'])
    if params.get('active') in ('true', 'false'):
      qs = qs.filter(is_active=params['active'] == 'true')
    team = params.get('team')
    if team:
      try:
        qs = qs.filter(team_memberships__team_id=uuid.UUID(team))
      except ValueError:
        pass
    return qs.distinct()

  @action(detail=True, methods=['post'], url_path='reset-password')
  def reset_password(self, request, pk=None):
    from notifications.account_mail import send_password_reset_notice
    user = self.get_object()
    if user.pk == request.user.pk:
      raise serializers.ValidationError(
        {'detail': 'Use Change password for your own account.'}
      )
    password = str(request.data.get('password', ''))
    if not password:
      raise serializers.ValidationError({'password': 'Enter the new temporary password.'})
    try:
      validate_password(password, user=user)
    except DjangoValidationError as exc:
      raise serializers.ValidationError({'password': list(exc.messages)})
    user.set_password(password)
    user.must_change_password = True
    user.save(update_fields=['password', 'must_change_password'])
    disconnect_user(user)
    notified = send_password_reset_notice(user, request.user)
    return Response({'detail': 'Password updated.', 'notified': notified})

  @action(detail=True, methods=['post'], url_path='send-reset-link')
  def send_link(self, request, pk=None):
    from notifications.account_mail import send_reset_link
    user = self.get_object()
    if not user.is_active:
      raise serializers.ValidationError({'detail': 'This account is deactivated.'})
    return Response({'detail': 'Link sent.', 'sent': send_reset_link(user)})
