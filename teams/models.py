import uuid

from django.db import models
from users.models import User


class ResponseTeam(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    team_name = models.CharField(max_length=150)

    leader = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="led_teams"
    )

    hotline_number = models.CharField(max_length=20)

    team_email = models.EmailField()

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.team_name


class TeamMember(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    team = models.ForeignKey(
        ResponseTeam,
        on_delete=models.CASCADE,
        related_name="members"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="team_memberships"
    )

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("team", "user")
        verbose_name = "Team Member"
        verbose_name_plural = "Team Members"

    def __str__(self):
        return f"{self.user.full_name} - {self.team.team_name}"


class EmergencyCategory(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    category_name = models.CharField(
        max_length=100,
        unique=True
    )

    team = models.ForeignKey(
        ResponseTeam,
        on_delete=models.CASCADE,
        related_name="categories"
    )

    is_custom = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.category_name
