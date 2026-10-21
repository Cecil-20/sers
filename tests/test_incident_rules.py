import pytest
from rest_framework.test import APIClient

from ai_module import services
from teams.models import ResponseTeam, TeamMember
from tests.factories import make_category, make_incident
from tests.helpers import PASSWORD, client_for, make_user, rows

pytestmark = pytest.mark.django_db

DELETE = {'password': PASSWORD, 'confirm': 'DELETE'}
ACTIONS = '/api/incident-actions/{}/'


@pytest.fixture(autouse=True)
def no_ai(monkeypatch):
  """Never call a real AI provider from a test."""
  monkeypatch.setattr(services, 'PROVIDERS', ())


@pytest.fixture
def category(team):
  return make_category(team)


@pytest.fixture
def other_team(db):
  return ResponseTeam.objects.create(
    team_name='Fire Unit', hotline_number='+254700000002', team_email='fire@example.com'
  )


@pytest.fixture
def other_leader(other_team):
  user = make_user('fireboss@example.com', 'team_leader')
  TeamMember.objects.create(team=other_team, user=user)
  other_team.leader = user
  other_team.save()
  return user


def ids(response):
  assert response.status_code == 200, response.data
  return {str(item['id']) for item in rows(response)}


# ---- who sees which incident ------------------------------------------------------

def test_leaders_only_see_their_own_teams_incidents(as_leader, as_admin, other_team, category, reporter_u):
  mine = make_incident(reporter_u, category)
  theirs = make_incident(reporter_u, make_category(other_team, 'Fire'))
  seen = ids(as_leader.get('/api/incidents/'))
  assert str(mine.id) in seen
  assert str(theirs.id) not in seen
  assert {str(mine.id), str(theirs.id)} <= ids(as_admin.get('/api/incidents/'))


def test_reporters_only_see_their_own_incidents(as_reporter, category, reporter_u):
  stranger = make_user('stranger@example.com')
  mine = make_incident(reporter_u, category)
  theirs = make_incident(stranger, category)
  seen = ids(as_reporter.get('/api/incidents/'))
  assert str(mine.id) in seen
  assert str(theirs.id) not in seen


def test_anonymous_users_see_nothing():
  assert APIClient().get('/api/incidents/').status_code == 401


# ---- admin rules that depend on incidents -----------------------------------------------

def test_a_team_with_open_incidents_cannot_be_deactivated(as_admin, team, category, reporter_u):
  incident = make_incident(reporter_u, category)
  r = as_admin.patch(f'/api/manage/teams/{team.id}/', {'is_active': False}, format='json')
  assert r.status_code == 400
  assert 'open incident' in str(r.data)
  incident.status = 'closed'
  incident.save()
  r = as_admin.patch(f'/api/manage/teams/{team.id}/', {'is_active': False}, format='json')
  assert r.status_code == 200, r.data


def test_the_team_list_counts_open_incidents(as_admin, team, category, reporter_u):
  make_incident(reporter_u, category)
  make_incident(reporter_u, category, status='closed')
  row = next(t for t in rows(as_admin.get('/api/manage/teams/')) if t['team_name'] == 'Medical Unit')
  assert row['open_incidents'] == 1


def test_a_category_in_use_cannot_be_deleted(as_admin, category, reporter_u):
  make_incident(reporter_u, category)
  r = as_admin.delete(f'/api/manage/categories/{category.id}/')
  assert r.status_code == 400
  assert 'cannot be deleted' in str(r.data)
  row = next(c for c in rows(as_admin.get('/api/manage/categories/')) if c['id'] == str(category.id))
  assert row['incident_count'] == 1


# ---- account deletion and export ---------------------------------------------------------

def test_account_deletion_waits_for_open_reports_then_keeps_them(as_reporter, reporter_u, category):
  incident = make_incident(reporter_u, category)
  blocked = as_reporter.post('/api/account/delete/', DELETE, format='json')
  assert blocked.status_code == 400
  assert 'still being handled' in str(blocked.data)
  incident.status = 'resolved'
  incident.save()
  assert as_reporter.post('/api/account/delete/', DELETE, format='json').status_code == 200
  incident.refresh_from_db()
  assert incident.reporter_id == reporter_u.id
  reporter_u.refresh_from_db()
  assert reporter_u.full_name == 'Deleted user'


def test_the_export_contains_only_my_incidents(as_reporter, reporter_u, category):
  mine = make_incident(reporter_u, category)
  theirs = make_incident(make_user('stranger@example.com'), category)
  r = as_reporter.get('/api/account/export/')
  assert r.status_code == 200, r.data
  text = str(r.data['incidents_reported'])
  assert mine.reference_no in text
  assert theirs.reference_no not in text


# ---- action log -------------------------------------------------------------------------

def test_a_team_leader_can_log_actions(as_leader, category, reporter_u):
  incident = make_incident(reporter_u, category)
  got = as_leader.get(ACTIONS.format(incident.id))
  assert got.status_code == 200 and got.data['can_write'] is True
  posted = as_leader.post(ACTIONS.format(incident.id), {'text': 'Ambulance dispatched.'}, format='json')
  assert posted.status_code in (200, 201), posted.data
  assert len(as_leader.get(ACTIONS.format(incident.id)).data['entries']) == 1


def test_empty_action_entries_are_refused(as_leader, category, reporter_u):
  incident = make_incident(reporter_u, category)
  r = as_leader.post(ACTIONS.format(incident.id), {'text': '   '}, format='json')
  assert r.status_code == 400


def test_other_teams_and_reporters_cannot_read_or_write_the_log(other_leader, as_reporter, category, reporter_u):
  incident = make_incident(reporter_u, category)
  for client in (client_for(other_leader), as_reporter):
    assert client.get(ACTIONS.format(incident.id)).status_code == 403
    assert client.post(ACTIONS.format(incident.id), {'text': 'hello'}, format='json').status_code == 403


def test_admins_can_log_actions(as_admin, category, reporter_u):
  incident = make_incident(reporter_u, category)
  assert as_admin.get(ACTIONS.format(incident.id)).data['can_write'] is True


def test_closed_incidents_are_read_only(as_leader, category, reporter_u):
  incident = make_incident(reporter_u, category, status='closed')
  got = as_leader.get(ACTIONS.format(incident.id))
  assert got.status_code == 200 and got.data['can_write'] is False
  assert as_leader.post(ACTIONS.format(incident.id), {'text': 'late note'}, format='json').status_code == 403


# ---- analytics and saved reports -----------------------------------------------------------

def test_dashboard_access(as_admin, as_leader, as_reporter):
  assert as_admin.get('/api/analytics/dashboard/').status_code == 200
  assert as_leader.get('/api/analytics/dashboard/').status_code == 200
  assert as_reporter.get('/api/analytics/dashboard/').status_code in (401, 403)


def test_a_report_pdf_is_generated_and_stays_with_its_team(as_leader, other_leader, category, reporter_u):
  make_incident(reporter_u, category)
  r = as_leader.post('/api/analytics/reports/generate/', {}, format='json')
  assert r.status_code in (200, 201), r.data
  url = f"/api/analytics/reports/{r.data['id']}/download/"
  pdf = as_leader.get(url)
  assert pdf.status_code == 200
  assert pdf.content.startswith(b'%PDF')
  assert client_for(other_leader).get(url).status_code in (403, 404)


# ---- AI fallbacks ------------------------------------------------------------------------------

def test_classification_survives_every_provider_failing(monkeypatch):
  def down(*args, **kwargs):
    raise RuntimeError('provider down')

  monkeypatch.setattr(services, 'PROVIDERS', (('gemini', down), ('groq', down)))
  result = services.classify_incident('Fire in the main kitchen', 'Fire')
  assert result['source'] == 'fallback'
  assert result['severity']


def test_the_reporter_assistant_falls_back_to_static_tips():
  result = services.assist_report('Fire in the main kitchen of the cafeteria', 'Fire')
  assert result['source'] == 'fallback'
  assert result['safety_tips']


def test_the_assistant_endpoint_needs_a_login_and_a_real_description(as_reporter):
  assert APIClient().post('/api/ai/assist/', {'description': 'Smoke in the library'}, format='json').status_code == 401
  assert as_reporter.post('/api/ai/assist/', {'description': 'fire'}, format='json').status_code == 400
