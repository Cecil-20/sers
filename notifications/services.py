import resend
from django.conf import settings
from .models import Notification
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

resend.api_key = settings.RESEND_API_KEY


def _group_send(group, payload):
    try:
        async_to_sync(get_channel_layer().group_send)(group, payload)
    except Exception as e:
        print(f'WebSocket broadcast error ({group}): {e}')


def dispatch_incident_notifications(incident, ai_result):
    subject = f'New Incident [{ai_result["severity"]}] — {incident.reference_no}'
    html_body = f"""
        <h2>New Incident Reported</h2>
        <p><strong>Category:</strong> {incident.category.category_name}</p>
        <p><strong>Description:</strong> {incident.description}</p>
        <p><strong>AI Severity:</strong> {ai_result['severity']}</p>
        <p><strong>AI Classification:</strong> {ai_result['classification']}</p>
        <p><strong>Recommended Protocol:</strong> {ai_result['protocol']}</p>
        <p><strong>Location:</strong> {incident.latitude}, {incident.longitude}</p>
    """
    delivery_status = 'sent'
    try:
        resend.Emails.send({
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": [incident.team.team_email],
            "subject": subject,
            "html": html_body,
        })
    except Exception as e:
        print(f'Resend API error: {e}')
        delivery_status = 'failed'
    Notification.objects.create(
        incident=incident, channel='email',
        recipient=incident.team.team_email, delivery_status=delivery_status
    )

    alert = {
        'type': 'incident_alert',
        'incident_id': str(incident.id),
        'reference_no': incident.reference_no,
        'severity': ai_result['severity'],
        'category': incident.category.category_name,
        'report_method': incident.report_method,
    }
    _group_send(f'team_{incident.team.id}', alert)
    _group_send('admins', alert)
    Notification.objects.create(
        incident=incident, channel='websocket',
        recipient=f'team_{incident.team.id}', delivery_status='sent'
    )


def broadcast_incident_status(incident, old_status, new_status):
    """Push a status change to the incident's team and to all admins."""
    payload = {
        'type': 'incident_status',
        'incident_id': str(incident.id),
        'reference_no': incident.reference_no,
        'old_status': old_status,
        'status': new_status,
    }
    if incident.team_id:
        _group_send(f'team_{incident.team_id}', payload)
    _group_send('admins', payload)
