from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from teams.models import TeamMember
from users.models import User
from .models import InAppNotification


def _push(notification):
    """Tell the user's open tabs about a new notification (best effort)."""
    try:
        unread = InAppNotification.objects.filter(
            user_id=notification.user_id, is_read=False
        ).count()
        async_to_sync(get_channel_layer().group_send)(
            f'user_{notification.user_id}',
            {
                'type': 'user_notification',
                'id': str(notification.id),
                'kind': notification.kind,
                'message': notification.message,
                'incident_id': str(notification.incident_id),
                'reference_no': notification.incident.reference_no,
                'created_at': notification.created_at.isoformat(),
                'unread_count': unread,
            },
        )
    except Exception as exc:
        print(f'In-app notification push error: {exc}')


def create_notification(user, incident, kind, message):
    notification = InAppNotification.objects.create(
        user=user, incident=incident, kind=kind, message=message
    )
    # Push only once the row is committed, so a client that reacts to the push
    # by re-fetching the count sees it.
    transaction.on_commit(lambda: _push(notification))
    return notification


def _category_name(incident):
    return incident.category.category_name if incident.category else 'Unknown category'


def notify_incident_reported(incident):
    """Every admin plus the incident's team (leader and members). Not the reporter."""
    recipient_ids = set(
        User.objects.filter(role='general_admin', is_active=True).values_list('id', flat=True)
    )
    if incident.team_id:
        recipient_ids |= set(
            TeamMember.objects.filter(team_id=incident.team_id).values_list('user_id', flat=True)
        )
    recipient_ids.discard(incident.reporter_id)

    severity = f' ({incident.ai_severity})' if incident.ai_severity else ''
    message = f'New incident {incident.reference_no}: {_category_name(incident)}{severity}'
    for user in User.objects.filter(id__in=recipient_ids, is_active=True):
        create_notification(user, incident, 'incident_reported', message)


def notify_assigned(incident, team_members, assigned_by):
    """Tell each newly assigned member (team_members need user preloaded)."""
    for member in team_members:
        if member.user_id == assigned_by.id:
            continue
        create_notification(
            member.user,
            incident,
            'assigned',
            f'You have been assigned to incident {incident.reference_no} '
            f'({_category_name(incident)}).',
        )


def notify_resolved(incident, resolved_by):
    """Tell whoever reported the incident that the team has resolved it."""
    reporter = incident.reporter
    if reporter is None or reporter.id == resolved_by.id:
        return
    create_notification(
        reporter,
        incident,
        'resolved',
        f'Incident {incident.reference_no} that you reported has been marked '
        f'resolved by the response team.',
    )
