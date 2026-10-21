import pytest
from django.core.cache import cache

from notifications import account_mail
from teams.models import ResponseTeam, TeamMember
from tests.helpers import client_for, make_user


@pytest.fixture(autouse=True)
def _isolated(settings, monkeypatch):
  """Fast hashing, in-memory cache and channel layer, and no real emails."""
  settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
  settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
  settings.CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
  cache.clear()
  sent = []

  def fake_send(to, subject, text):
    sent.append({'to': to, 'subject': subject, 'text': text})
    return True

  monkeypatch.setattr(account_mail, '_send', fake_send)
  return sent


@pytest.fixture
def outbox(_isolated):
  return _isolated


@pytest.fixture
def team(db):
  return ResponseTeam.objects.create(
    team_name='Medical Unit', hotline_number='+254700000001', team_email='medical@example.com'
  )


@pytest.fixture
def admin_u(db):
  return make_user('admin@example.com', 'general_admin')


@pytest.fixture
def leader_u(db, team):
  user = make_user('leader@example.com', 'team_leader')
  TeamMember.objects.create(team=team, user=user)
  team.leader = user
  team.save()
  return user


@pytest.fixture
def member_u(db, team):
  user = make_user('member@example.com', 'team_member')
  TeamMember.objects.create(team=team, user=user)
  return user


@pytest.fixture
def reporter_u(db):
  return make_user('reporter@example.com', 'general_user')


@pytest.fixture
def as_admin(admin_u):
  return client_for(admin_u)


@pytest.fixture
def as_leader(leader_u):
  return client_for(leader_u)


@pytest.fixture
def as_reporter(reporter_u):
  return client_for(reporter_u)
