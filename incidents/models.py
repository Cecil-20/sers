import uuid
import random
import string

from django.db import models
from users.models import User
from teams.models import ResponseTeam, EmergencyCategory


class Incident(models.Model):
    REPORT_METHOD_CHOICES = [
        ('hotline', 'Hotline'),
        ('form', 'Form/Email'),
    ]

    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    reference_no = models.CharField(
        max_length=20,
        unique=True,
        editable=False
    )

    reporter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reported_incidents'
    )

    category = models.ForeignKey(
        EmergencyCategory,
        on_delete=models.SET_NULL,
        null=True
    )

    team = models.ForeignKey(
        ResponseTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents'
    )

    report_method = models.CharField(
        max_length=10,
        choices=REPORT_METHOD_CHOICES
    )

    # Phone number of the caller, for incidents logged from the hotline.
    caller_number = models.CharField(max_length=20, blank=True, default='')

    description = models.TextField()

    custom_type_text = models.CharField(
        max_length=150,
        blank=True
    )

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='submitted'
    )

    ai_severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        blank=True
    )

    ai_classification = models.CharField(
        max_length=100,
        blank=True
    )

    ai_protocol = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    resolved_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def save(self, *args, **kwargs):
        if not self.reference_no:
            self.reference_no = "INC-" + "".join(
                random.choices(string.digits, k=8)
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.reference_no


class IncidentImage(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name='images'
    )

    image = models.ImageField(
        upload_to='incident_images/'
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Image for {self.incident.reference_no}"


class ResponderAssignment(models.Model):
    STATUS_CHOICES = [
        ('assigned', 'Assigned'),
        ('acknowledged', 'Acknowledged'),
        ('completed', 'Completed'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name='assignments'
    )

    team_member = models.ForeignKey(
        'teams.TeamMember',
        on_delete=models.CASCADE
    )

    assigned_at = models.DateTimeField(
        auto_now_add=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='assigned'
    )

    def __str__(self):
        return f"{self.team_member} - {self.incident.reference_no}"


class IncidentStatusLog(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name='status_log'
    )

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    old_status = models.CharField(
        max_length=30
    )

    new_status = models.CharField(
        max_length=30
    )

    notes = models.TextField(
        blank=True
    )

    timestamp = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.incident.reference_no} - {self.new_status}"



import uuid as _uuid
from django.conf import settings as _settings


class IncidentAction(models.Model):
  """A line in an incident's action log: what the team did, and when."""
  id = models.UUIDField(primary_key=True, default=_uuid.uuid4, editable=False)
  incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='actions')
  author = models.ForeignKey(
    _settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    related_name='incident_actions',
  )
  text = models.CharField(max_length=500)
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    ordering = ['created_at']

  def __str__(self):
    return f'{self.incident.reference_no}: {self.text[:40]}'
