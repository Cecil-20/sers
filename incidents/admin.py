from django.contrib import admin
from .models import (
    Incident,
    IncidentImage,
    ResponderAssignment,
    IncidentStatusLog,
)


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = (
        "reference_no",
        "category",
        "reporter",
        "team",
        "status",
        "ai_severity",
        "created_at",
    )

    list_filter = (
        "status",
        "ai_severity",
        "report_method",
        "category",
    )

    search_fields = (
        "reference_no",
        "description",
        "ai_classification",
    )


@admin.register(IncidentImage)
class IncidentImageAdmin(admin.ModelAdmin):
    list_display = (
        "incident",
        "uploaded_at",
	"image",
    )
    list_filter = ("uploaded_at",)

    search_fields = ("incident_reference_no",)


@admin.register(ResponderAssignment)
class ResponderAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "incident",
        "team_member",
        "status",
        "assigned_at",
    )

    list_filter = ("status","assigned_at",)

    search_fields = ("incident__reference_no","team_member__user__username",)


@admin.register(IncidentStatusLog)
class IncidentStatusLogAdmin(admin.ModelAdmin):
    list_display = (
        "incident",
        "old_status",
        "new_status",
        "updated_by",
        "timestamp",
    )

    list_filter = (
        "new_status",
        "timestamp",
	"old_status",
    )

    search_fields = ("incident__reference_no", "old_status", "new_status", "notes",)
