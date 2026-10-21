from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient
from users.models import User
from teams.models import ResponseTeam, EmergencyCategory


class IncidentAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123",
            full_name="Test User", role="general_user")
        self.admin = User.objects.create_user(
            email="admin@example.com", password="adminpass123",
            full_name="Admin", role="general_admin")
        self.team = ResponseTeam.objects.create(
            team_name="Fire Response", hotline_number="0700000000",
            team_email="fire@serims.local")
        self.category = EmergencyCategory.objects.create(
            category_name="Fire", team=self.team)

        patcher_ai = patch("incidents.views.classify_incident")
        self.mock_classify = patcher_ai.start()
        self.mock_classify.return_value = {
            "severity": "Medium", "classification": "Fire",
            "protocol": "Dispatch immediately.",
        }
        self.addCleanup(patcher_ai.stop)

        patcher_notify = patch("incidents.views.dispatch_incident_notifications")
        self.mock_notify = patcher_notify.start()
        self.addCleanup(patcher_notify.stop)

    def test_incident_creation_routes_to_correct_team(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/incidents/", {
            "category": str(self.category.id),
            "report_method": "form",
            "description": "Small fire in the server room",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["team"], self.team.id)

    def test_unauthenticated_user_cannot_report(self):
        response = self.client.post("/api/incidents/", {})
        self.assertEqual(response.status_code, 401)

    def test_general_user_cannot_see_others_incidents(self):
        other_user = User.objects.create_user(
            email="other@example.com", password="pass123",
            full_name="Other", role="general_user")
        self.client.force_authenticate(user=self.user)
        self.client.post("/api/incidents/", {
            "category": str(self.category.id), "report_method": "form",
            "description": "Test incident"})
        self.client.force_authenticate(user=other_user)
        response = self.client.get("/api/incidents/")
        self.assertEqual(len(response.data), 0)

    def test_admin_can_see_all_incidents(self):
        self.client.force_authenticate(user=self.user)
        self.client.post("/api/incidents/", {
            "category": str(self.category.id), "report_method": "form",
            "description": "Test incident"})
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/incidents/")
        self.assertEqual(len(response.data), 1)
