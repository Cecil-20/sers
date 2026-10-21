import uuid

from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, permissions, status as http_status
from rest_framework.decorators import action
from rest_framework.response import Response

from teams.models import TeamMember
from .models import Incident, ResponderAssignment, IncidentStatusLog
from .serializers import IncidentSerializer
from .pipeline import finalize_new_incident
from notifications.services import broadcast_incident_status
from notifications.inapp import notify_assigned, notify_resolved

VALID_STATUSES = {'submitted', 'assigned', 'in_progress', 'resolved', 'closed'}
ASSIGNABLE_STATUSES = {'submitted', 'assigned', 'in_progress'}

# new_status -> statuses it may be reached from
LEADER_TRANSITIONS = {
    'in_progress': {'assigned'},
    'closed': {'resolved'},
}
MEMBER_TRANSITIONS = {
    'resolved': {'assigned', 'in_progress'},
}


class IncidentViewSet(viewsets.ModelViewSet):
    serializer_class = IncidentSerializer
    permission_classes = [permissions.IsAuthenticated]
    # Create + read only. Status and assignment changes go through the
    # dedicated actions below so every change is permission-checked and logged.
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Incident.objects.none()
        user = self.request.user
        if user.role == 'general_admin':
            return Incident.objects.all()
        if user.role in ('team_leader', 'team_member'):
            return Incident.objects.filter(team__members__user=user)
        return Incident.objects.filter(reporter=user)

    def perform_create(self, serializer):
        incident = serializer.save(
            reporter=self.request.user,
            team=serializer.validated_data['category'].team
        )
        finalize_new_incident(incident)

    @action(detail=True, methods=['get'], url_path=r'photos/(?P<image_id>[^/.]+)')
    def photo(self, request, pk=None, image_id=None):
        # get_object() goes through get_queryset(), so anyone who cannot see
        # the incident gets a 404 here, exactly as for the incident itself.
        incident = self.get_object()
        try:
            image_uuid = uuid.UUID(str(image_id))
        except ValueError:
            raise Http404
        image = get_object_or_404(incident.images, pk=image_uuid)
        seconds = 300
        url = image.image.storage.signed_url(image.image.name, seconds)
        response = Response({'url': url, 'expires_in': seconds})
        response['Cache-Control'] = 'no-store'
        return response

    # ---- helpers -----------------------------------------------------

    def _can_manage(self, user, incident):
        """General admin, or a team leader who belongs to the incident's team."""
        if user.role == 'general_admin':
            return True
        return (
            user.role == 'team_leader'
            and incident.team_id is not None
            and TeamMember.objects.filter(team_id=incident.team_id, user=user).exists()
        )

    def _responders_payload(self, incident):
        assigned = {a.team_member_id: a.status for a in incident.assignments.all()}
        members = TeamMember.objects.filter(team_id=incident.team_id).select_related('user')
        return [
            {
                'team_member_id': str(m.id),
                'user_id': str(m.user_id),
                'full_name': m.user.full_name or m.user.email,
                'role': m.user.role,
                'assigned': m.id in assigned,
                'assignment_status': assigned.get(m.id),
            }
            for m in members
        ]

    def _deny(self, message, code=http_status.HTTP_403_FORBIDDEN):
        return Response({'detail': message}, status=code)

    # ---- actions -----------------------------------------------------

    @action(detail=True, methods=['get'], url_path='responders')
    def responders(self, request, pk=None):
        """Team members of the incident's team, flagged with who is assigned."""
        incident = self.get_object()
        if request.user.role not in ('team_leader', 'team_member', 'general_admin'):
            return self._deny('You do not have access to responder details.')
        return Response(self._responders_payload(incident))

    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None):
        """Set the responders for an incident (replaces the current set)."""
        incident = self.get_object()
        if not self._can_manage(request.user, incident):
            return self._deny('Only the incident\'s team leader can assign responders.')
        if incident.status not in ASSIGNABLE_STATUSES:
            return self._deny(
                f"Cannot change assignments on a '{incident.status}' incident.",
                http_status.HTTP_400_BAD_REQUEST,
            )

        raw_ids = request.data.get('team_member_ids')
        if not isinstance(raw_ids, list) or not raw_ids:
            return self._deny(
                'team_member_ids must be a non-empty list.',
                http_status.HTTP_400_BAD_REQUEST,
            )
        try:
            ids = {uuid.UUID(str(i)) for i in raw_ids}
        except ValueError:
            return self._deny(
                'team_member_ids contains an invalid id.',
                http_status.HTTP_400_BAD_REQUEST,
            )

        members = list(
            TeamMember.objects.filter(id__in=ids, team_id=incident.team_id).select_related('user')
        )
        if len(members) != len(ids):
            return self._deny(
                "One or more members do not belong to this incident's team.",
                http_status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            existing = set(incident.assignments.values_list('team_member_id', flat=True))
            incident.assignments.exclude(team_member_id__in=ids).delete()
            newly_added = []
            for member in members:
                if member.id not in existing:
                    ResponderAssignment.objects.create(incident=incident, team_member=member)
                    newly_added.append(member)

            old_status = incident.status
            if old_status == 'submitted':
                incident.status = 'assigned'
                incident.save()

            names = ', '.join(m.user.full_name or m.user.email for m in members)
            IncidentStatusLog.objects.create(
                incident=incident,
                updated_by=request.user,
                old_status=old_status,
                new_status=incident.status,
                notes=f'Assigned to: {names}',
            )
            notify_assigned(incident, newly_added, request.user)
            new_status = incident.status
            transaction.on_commit(
                lambda: broadcast_incident_status(incident, old_status, new_status)
            )

        return Response(self._responders_payload(incident))

    @action(detail=True, methods=['post'], url_path='status')
    def change_status(self, request, pk=None):
        """Leader: assigned -> in_progress, resolved -> closed.
        Assigned member: assigned/in_progress -> resolved."""
        incident = self.get_object()
        user = request.user
        new_status = request.data.get('status')
        notes = request.data.get('notes', '')

        if new_status not in VALID_STATUSES:
            return self._deny('Unknown status.', http_status.HTTP_400_BAD_REQUEST)

        if self._can_manage(user, incident):
            allowed = LEADER_TRANSITIONS
        elif (
            user.role == 'team_member'
            and ResponderAssignment.objects.filter(
                incident=incident, team_member__user=user
            ).exists()
        ):
            allowed = MEMBER_TRANSITIONS
        else:
            return self._deny('You are not allowed to update this incident\'s status.')

        if new_status not in allowed:
            return self._deny(f"Your role cannot set the status to '{new_status}'.")
        if incident.status not in allowed[new_status]:
            return self._deny(
                f"Cannot move an incident from '{incident.status}' to '{new_status}'.",
                http_status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            old_status = incident.status
            incident.status = new_status
            if new_status == 'resolved':
                incident.resolved_at = timezone.now()
            incident.save()

            IncidentStatusLog.objects.create(
                incident=incident,
                updated_by=user,
                old_status=old_status,
                new_status=new_status,
                notes=notes,
            )

            if new_status == 'in_progress':
                incident.assignments.filter(status='assigned').update(status='acknowledged')
            elif new_status == 'resolved':
                incident.assignments.filter(team_member__user=user).update(status='completed')
                notify_resolved(incident, user)

            transaction.on_commit(
                lambda: broadcast_incident_status(incident, old_status, new_status)
            )

        return Response(IncidentSerializer(incident, context={'request': request}).data)
