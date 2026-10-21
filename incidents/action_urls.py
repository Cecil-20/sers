from django.urls import path
from .action_log import IncidentActionView

urlpatterns = [
    path('<uuid:incident_id>/', IncidentActionView.as_view(), name='incident-actions'),
]
