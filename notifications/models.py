import uuid
from django.db import models
from incidents.models import Incident
from django.conf import settings
# Create your models here.
class Notification(models.Model):
	CHANNEL_CHOICES = [('email', 'Email'), ('websocket', 'Websocket')]
	STATUS_CHOICES = [('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed')]
	id = models.UUIDField(primary_key = True, default = uuid.uuid4, editable=False)
	incident = models.ForeignKey(Incident,  on_delete=models.CASCADE, related_name='notifications')
	channel = models.CharField(max_length = 15, choices=CHANNEL_CHOICES)
	recipient = models.CharField(max_length = 150)
	delivery_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
	sent_at = models.DateTimeField(auto_now_add=True)

class InAppNotification(models.Model):
        """A message shown to one user in the app (bell icon + notifications page)."""
        KIND_CHOICES = [
            ('incident_reported', 'Incident reported'),
            ('assigned', 'Assigned to an incident'),
            ('resolved', 'Incident resolved'),
        ]

        id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        user = models.ForeignKey(
            settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='in_app_notifications'
        )
        incident = models.ForeignKey(
            Incident, on_delete=models.CASCADE, related_name='in_app_notifications'
        )
        kind = models.CharField(max_length=20, choices=KIND_CHOICES)
        message = models.CharField(max_length=255)
        is_read = models.BooleanField(default=False)
        created_at = models.DateTimeField(auto_now_add=True)

        class Meta:
            ordering = ['-created_at']
            indexes = [models.Index(fields=['user', 'is_read'])]

        def __str__(self):
            return f"{self.user} - {self.kind} - {self.incident.reference_no}" 
