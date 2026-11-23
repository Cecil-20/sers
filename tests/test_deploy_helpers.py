import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from users.models import User

pytestmark = pytest.mark.django_db

GOOD = {
  'ADMIN_EMAIL': 'First.Admin@example.com',
  'ADMIN_PASSWORD': 'Str0ng-Pass-9271',
  'ADMIN_NAME': 'First Admin',
}


def run(monkeypatch, **env):
  for key in ('ADMIN_EMAIL', 'ADMIN_PASSWORD', 'ADMIN_NAME'):
    monkeypatch.delenv(key, raising=False)
  for key, value in env.items():
    monkeypatch.setenv(key, value)
  call_command('ensure_admin')


def test_health_check_is_public():
  res = APIClient().get('/healthz/')
  assert res.status_code == 200
  assert res.json() == {'status': 'ok'}


def test_creates_the_first_admin_with_a_forced_password_change(monkeypatch):
  run(monkeypatch, **GOOD)
  user = User.objects.get(role='general_admin')
  assert user.email == 'first.admin@example.com'
  assert user.must_change_password is True
  assert user.check_password(GOOD['ADMIN_PASSWORD'])


def test_does_nothing_when_an_admin_exists(admin_u, monkeypatch):
  run(monkeypatch, **GOOD)
  assert User.objects.filter(role='general_admin').count() == 1


def test_skips_when_not_configured(monkeypatch):
  run(monkeypatch)
  assert not User.objects.exists()


def test_refuses_a_weak_password(monkeypatch):
  with pytest.raises(CommandError):
    run(monkeypatch, ADMIN_EMAIL='a@example.com', ADMIN_PASSWORD='12345678')
  assert not User.objects.exists()
