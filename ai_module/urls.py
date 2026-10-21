from django.urls import path
from .assist_views import ReportAssistView

urlpatterns = [
    path('assist/', ReportAssistView.as_view(), name='ai-assist'),
]
