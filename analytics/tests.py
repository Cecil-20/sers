from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient
from users.models import User
from teams.models import ResponseTeam, EmergencyCategory
from incidents.models import Incident
from analytics.models import AnalyticsReport


class AnalyticsDashboardTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin@example.com", password="adminpass123",
            full_name="Admin", role="general_admin")
        self.leader = User.objects.create_user(
            email="leader@example.com", password="leaderpass123",
            full_name="Leader", role="team_leader")
        self.reporter = User.objects.create_user(
            email="reporter@example.com", password="reporterpass123",
            full_name="Reporter", role="general_user")
        self.team = ResponseTeam.objects.create(
            team_name="Fire Response", hotline_number="0700000000",
            team_email="fire@serims.local")
        self.category = EmergencyCategory.objects.create(
            category_name="Fire", team=self.team)

        patcher_ai = patch("incidents.views.classify_incident")
        self.mock_classify = patcher_ai.start()
        self.mock_classify.return_value = {
            "severity": "High", "classification": "Fire",
            "protocol": "Dispatch immediately.",
        }
        self.addCleanup(patcher_ai.stop)

        patcher_notify = patch("incidents.views.dispatch_incident_notifications")
        self.mock_notify = patcher_notify.start()
        self.addCleanup(patcher_notify.stop)

    def _create_incident(self, description="Test incident"):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.post("/api/incidents/", {
            "category": str(self.category.id),
            "report_method": "form",
            "description": description,
        })
        self.assertEqual(response.status_code, 201)
        return response.data

    def test_unauthenticated_cannot_access_dashboard(self):
        response = self.client.get("/api/analytics/dashboard/")
        self.assertEqual(response.status_code, 401)

    def test_general_user_cannot_access_dashboard(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/analytics/dashboard/")
        self.assertEqual(response.status_code, 403)

    def test_team_leader_can_access_dashboard(self):
        self.client.force_authenticate(user=self.leader)
        response = self.client.get("/api/analytics/dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_dashboard(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/analytics/dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_returns_expected_keys(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/analytics/dashboard/")
        expected_keys = {
            "total_incidents", "by_status", "by_category",
            "by_severity", "average_response_time_seconds",
        }
        self.assertTrue(expected_keys.issubset(response.data.keys()))

    def test_dashboard_total_incidents_reflects_created_incidents(self):
        self._create_incident("First incident")
        self._create_incident("Second incident")
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/analytics/dashboard/")
        self.assertEqual(response.data["total_incidents"], 2)

    def test_dashboard_with_zero_incidents_does_not_error(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/analytics/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_incidents"], 0)
        self.assertIsNone(response.data["average_response_time_seconds"])


class AnalyticsReportTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin2@example.com", password="adminpass123",
            full_name="Admin Two", role="general_admin")
        self.leader = User.objects.create_user(
            email="leader2@example.com", password="leaderpass123",
            full_name="Leader Two", role="team_leader")
        self.reporter = User.objects.create_user(
            email="reporter2@example.com", password="reporterpass123",
            full_name="Reporter Two", role="general_user")

    def test_unauthenticated_cannot_list_reports(self):
        response = self.client.get("/api/analytics/reports/")
        self.assertEqual(response.status_code, 401)

    def test_general_user_cannot_create_report(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.post("/api/analytics/reports/", {
            "report_type": "monthly_summary",
            "date_range_start": "2026-09-01",
            "date_range_end": "2026-09-30",
        })
        self.assertEqual(response.status_code, 403)

    def test_team_leader_can_create_report(self):
        self.client.force_authenticate(user=self.leader)
        response = self.client.post("/api/analytics/reports/", {
            "report_type": "monthly_summary",
            "date_range_start": "2026-09-01",
            "date_range_end": "2026-09-30",
        })
        self.assertEqual(response.status_code, 201)

    def test_report_generated_by_is_set_to_requesting_user(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/analytics/reports/", {
            "report_type": "monthly_summary",
            "date_range_start": "2026-09-01",
            "date_range_end": "2026-09-30",
        })
        self.assertEqual(response.status_code, 201)
        report = AnalyticsReport.objects.get(id=response.data["id"])
        self.assertEqual(report.generated_by, self.admin)

    def test_report_list_returns_created_reports(self):
        self.client.force_authenticate(user=self.admin)
        self.client.post("/api/analytics/reports/", {
            "report_type": "weekly_summary",
            "date_range_start": "2026-10-01",
            "date_range_end": "2026-10-07",
        })
        response = self.client.get("/api/analytics/reports/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_reports_are_ordered_most_recent_first(self):
        self.client.force_authenticate(user=self.admin)
        self.client.post("/api/analytics/reports/", {
            "report_type": "first_report",
            "date_range_start": "2026-08-01",
            "date_range_end": "2026-08-31",
        })
        self.client.post("/api/analytics/reports/", {
            "report_type": "second_report",
            "date_range_start": "2026-09-01",
            "date_range_end": "2026-09-30",
        })
        response = self.client.get("/api/analytics/reports/")
        self.assertEqual(response.data[0]["report_type"], "second_report")
