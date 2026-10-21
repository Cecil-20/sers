from django.test import TestCase
from rest_framework.test import APIClient
from users.models import User
from teams.models import ResponseTeam, TeamMember, EmergencyCategory


class TeamAPITestCase(TestCase):
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
            team_name="Fire Response", leader=self.leader,
            hotline_number="0700000000", team_email="fire@serims.local")
        TeamMember.objects.create(team=self.team, user=self.leader)
        self.category = EmergencyCategory.objects.create(
            category_name="Fire", team=self.team)

    def test_admin_can_create_team(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/teams/response-teams/", {
            "team_name": "Medical Response",
            "hotline_number": "0711111111",
            "team_email": "medical@serims.local",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            ResponseTeam.objects.filter(team_name="Medical Response").count(), 1)

    def test_non_admin_cannot_create_team(self):
        self.client.force_authenticate(user=self.leader)
        response = self.client.post("/api/teams/response-teams/", {
            "team_name": "Unauthorized Team",
            "hotline_number": "0722222222",
            "team_email": "nope@serims.local",
        })
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_cannot_create_team(self):
        response = self.client.post("/api/teams/response-teams/", {
            "team_name": "No Auth Team",
            "hotline_number": "0733333333",
            "team_email": "noauth@serims.local",
        })
        self.assertEqual(response.status_code, 401)

    def test_any_authenticated_user_can_list_teams(self):
        self.client.force_authenticate(user=self.reporter)
        response = self.client.get("/api/teams/response-teams/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_admin_can_create_category(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/teams/categories/", {
            "category_name": "Flood",
            "team": str(self.team.id),
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["team"], self.team.id)

    def test_non_admin_cannot_create_category(self):
        self.client.force_authenticate(user=self.leader)
        response = self.client.post("/api/teams/categories/", {
            "category_name": "Unauthorized Category",
            "team": str(self.team.id),
        })
        self.assertEqual(response.status_code, 403)

    def test_category_is_correctly_linked_to_its_team(self):
        self.assertEqual(self.category.team.id, self.team.id)
        self.assertEqual(self.team.categories.count(), 1)

    def test_team_member_relationship_created_correctly(self):
        self.assertTrue(
            TeamMember.objects.filter(team=self.team, user=self.leader).exists())
        self.assertEqual(self.leader.team_memberships.first().team, self.team)
