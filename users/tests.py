from django.test import TestCase
from rest_framework.test import APIClient
from users.models import User


class UserModelTestCase(TestCase):
    def test_create_user_sets_fields_and_role_correctly(self):
        user = User.objects.create_user(
            email="newuser@example.com", password="pass123456",
            full_name="New User", role="general_user")
        self.assertEqual(user.email, "newuser@example.com")
        self.assertEqual(user.role, "general_user")
        self.assertTrue(user.check_password("pass123456"))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)

    def test_create_superuser_sets_admin_flags_and_role(self):
        admin = User.objects.create_superuser(
            email="superadmin@example.com", password="superpass123",
            full_name="Super Admin")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, "general_admin")

    def test_user_string_representation(self):
        user = User.objects.create_user(
            email="strtest@example.com", password="pass123456",
            full_name="String Test", role="team_member")
        self.assertEqual(str(user), "String Test (team_member)")

    def test_email_is_unique(self):
        User.objects.create_user(
            email="duplicate@example.com", password="pass123456",
            full_name="First", role="general_user")
        with self.assertRaises(Exception):
            User.objects.create_user(
                email="duplicate@example.com", password="pass123456",
                full_name="Second", role="general_user")


class AuthenticationAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="authuser@example.com", password="correctpass123",
            full_name="Auth User", role="general_user")

    def test_login_with_correct_credentials_returns_tokens(self):
        response = self.client.post("/api/auth/login/", {
            "email": "authuser@example.com",
            "password": "correctpass123",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_wrong_password_fails(self):
        response = self.client.post("/api/auth/login/", {
            "email": "authuser@example.com",
            "password": "wrongpassword",
        })
        self.assertEqual(response.status_code, 401)

    def test_login_with_nonexistent_email_fails(self):
        response = self.client.post("/api/auth/login/", {
            "email": "doesnotexist@example.com",
            "password": "whatever123",
        })
        self.assertEqual(response.status_code, 401)

    def test_token_refresh_returns_new_access_token(self):
        login_response = self.client.post("/api/auth/login/", {
            "email": "authuser@example.com",
            "password": "correctpass123",
        })
        refresh_token = login_response.data["refresh"]
        refresh_response = self.client.post("/api/auth/refresh/", {
            "refresh": refresh_token,
        })
        self.assertEqual(refresh_response.status_code, 200)
        self.assertIn("access", refresh_response.data)

    def test_protected_endpoint_rejects_missing_token(self):
        response = self.client.get("/api/incidents/")
        self.assertEqual(response.status_code, 401)

    def test_protected_endpoint_rejects_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.value")
        response = self.client.get("/api/incidents/")
        self.assertEqual(response.status_code, 401)

    def test_protected_endpoint_accepts_valid_token(self):
        login_response = self.client.post("/api/auth/login/", {
            "email": "authuser@example.com",
            "password": "correctpass123",
        })
        access_token = login_response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get("/api/incidents/")
        self.assertEqual(response.status_code, 200)
