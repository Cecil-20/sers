from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Incident, IncidentAction, ResponderAssignment


class IncidentActionSerializer(serializers.ModelSerializer):
  author_name = serializers.SerializerMethodField()
  author_role = serializers.CharField(source='author.role', read_only=True, default=None)

  class Meta:
    model = IncidentAction
    fields = ['id', 'text', 'created_at', 'author_name', 'author_role']
    read_only_fields = ['id', 'created_at', 'author_name', 'author_role']

  def get_author_name(self, obj):
    if not obj.author:
      return 'Former user'
    return getattr(obj.author, 'full_name', None) or obj.author.email


def _on_team(user, incident):
  if not incident.team_id:
    return False
  return user.team_memberships.filter(team_id=incident.team_id).exists()


def _can_read(user, incident):
  if user.role == 'general_admin':
    return True
  return user.role in ('team_leader', 'team_member') and _on_team(user, incident)


def _can_write(user, incident):
  if user.role == 'general_admin':
    return True
  if user.role == 'team_leader':
    return _on_team(user, incident)
  if user.role == 'team_member':
    return ResponderAssignment.objects.filter(
      incident=incident, team_member__user=user
    ).exists()
  return False


class IncidentActionView(APIView):
  """GET: the action log. POST: add an entry (assigned team, leader or admin)."""
  permission_classes = [permissions.IsAuthenticated]

  def get(self, request, incident_id):
    incident = get_object_or_404(Incident, pk=incident_id)
    if not _can_read(request.user, incident):
      raise PermissionDenied('You do not have access to this incident log.')
    entries = incident.actions.select_related('author')
    return Response({
      'can_write': incident.status != 'closed' and _can_write(request.user, incident),
      'entries': IncidentActionSerializer(entries, many=True).data,
    })

  def post(self, request, incident_id):
    incident = get_object_or_404(Incident, pk=incident_id)
    if not _can_read(request.user, incident):
      raise PermissionDenied('You do not have access to this incident log.')
    if incident.status == 'closed':
      raise PermissionDenied('This incident is closed, so its log can no longer be changed.')
    if not _can_write(request.user, incident):
      raise PermissionDenied('Only the assigned team can log actions on this incident.')
    serializer = IncidentActionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    entry = serializer.save(incident=incident, author=request.user)
    return Response(IncidentActionSerializer(entry).data, status=status.HTTP_201_CREATED)
