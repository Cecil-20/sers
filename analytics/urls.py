from django.urls import path
from .views import AnalyticsDashboardView
from .report_views import (
    GenerateReportView, HotspotsView, ReportDownloadView, ReportListView,
)

urlpatterns = [
    path("dashboard/", AnalyticsDashboardView.as_view(), name="analytics-dashboard"),
    path("hotspots/", HotspotsView.as_view(), name="analytics-hotspots"),
    path("reports/", ReportListView.as_view(), name="analytics-reports"),
    path("reports/generate/", GenerateReportView.as_view(), name="analytics-report-generate"),
    path("reports/<uuid:pk>/download/", ReportDownloadView.as_view(), name="analytics-report-download"),
]
