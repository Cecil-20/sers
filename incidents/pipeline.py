from ai_module.services import classify_incident
from notifications.services import dispatch_incident_notifications
from notifications.inapp import notify_incident_reported


def finalize_new_incident(incident):
    """Everything that happens after a new incident row exists: AI
    classification, email + live alerts, and in-app notifications."""
    ai_result = classify_incident(
        description=incident.description,
        category=incident.category.category_name,
    )
    incident.ai_severity = ai_result['severity'].lower()
    incident.ai_classification = ai_result['classification'][:100]
    incident.ai_protocol = ai_result.get('protocol', '')
    incident.save()
    dispatch_incident_notifications(incident, ai_result)
    notify_incident_reported(incident)
    return ai_result
