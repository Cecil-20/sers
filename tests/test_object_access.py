import pytest
from rest_framework.test import APIClient

from core.permissions import IsOwnerOrAdmin
from incidents.models import IncidentStatusLog, ResponderAssignment
from teams.models import ResponseTeam, TeamMember
from tests.factories import make_category, make_incident
from tests.helpers import client_for, make_user

pytestmark = pytest.mark.django_db

ZERO_ID = '00000000-0000-0000-0000-000000000000'

# method, path suffix, request body
ENDPOINTS = [
  ('get', '', None),
  ('get', 'responders/', None),
  ('post', 'assign/', {'team_member_ids': [ZERO_ID]}),
  ('post', 'status/', {'status': 'in_progress'}),
]


def call(client, method, url, body):
  if body is None:
    return getattr(client, method)(url)
  return getattr(client, method)(url, body, format='json')


def base(incident):
  return f'/api/incidents/{incident.pk}/'


def assign_body(user):
  member = TeamMember.objects.get(user=user)
  return {'team_member_ids': [str(member.id)]}


@pytest.fixture
def incident(team, reporter_u):
  return make_incident(reporter_u, make_category(team))


@pytest.fixture
def other_team(db):
  return ResponseTeam.objects.create(
    team_name='Fire Unit', hotline_number='+254700000002', team_email='fire@example.com'
  )


@pytest.fixture
def other_leader(other_team):
  user = make_user('fire.leader@example.com', 'team_leader')
  TeamMember.objects.create(team=other_team, user=user)
  other_team.leader = user
  other_team.save()
  return user


@pytest.fixture
def other_member(other_team):
  user = make_user('fire.member@example.com', 'team_member')
  TeamMember.objects.create(team=other_team, user=user)
  return user


@pytest.fixture
def other_reporter(db):
  return make_user('other.reporter@example.com')


@pytest.fixture(params=['other_leader', 'other_member', 'other_reporter'])
def outsider(request):
  return client_for(request.getfixturevalue(request.param))


@pytest.fixture
def assigned_incident(incident, member_u):
  incident.status = 'assigned'
  incident.save()
  ResponderAssignment.objects.create(
    incident=incident, team_member=TeamMember.objects.get(user=member_u)
  )
  return incident


# ---- people outside the incident's team and not its reporter ----------

@pytest.mark.parametrize('method,suffix,body', ENDPOINTS)
def test_outsiders_cannot_even_see_the_incident(outsider, incident, method, suffix, body):
  assert call(outsider, method, base(incident) + suffix, body).status_code == 404


@pytest.mark.parametrize('method,suffix,body', ENDPOINTS)
def test_anonymous_users_are_refused(incident, method, suffix, body):
  assert call(APIClient(), method, base(incident) + suffix, body).status_code == 401


def test_rejected_calls_change_nothing(other_leader, incident, member_u):
  logs_before = IncidentStatusLog.objects.count()
  client = client_for(other_leader)
  client.post(base(incident) + 'assign/', assign_body(member_u), format='json')
  client.post(base(incident) + 'status/', {'status': 'in_progress'}, format='json')
  incident.refresh_from_db()
  assert incident.status == 'submitted'
  assert not ResponderAssignment.objects.exists()
  assert IncidentStatusLog.objects.count() == logs_before


# ---- people who can see it but may not manage it -----------------------

def test_reporter_reads_own_incident_but_cannot_manage(as_reporter, incident, member_u):
  b = base(incident)
  assert as_reporter.get(b).status_code == 200
  assert as_reporter.get(b + 'responders/').status_code == 403
  assert as_reporter.post(b + 'assign/', assign_body(member_u), format='json').status_code == 403
  assert as_reporter.post(b + 'status/', {'status': 'in_progress'}, format='json').status_code == 403


def test_unassigned_member_cannot_assign_or_resolve(member_u, incident):
  incident.status = 'assigned'
  incident.save()
  client = client_for(member_u)
  b = base(incident)
  assert client.post(b + 'assign/', assign_body(member_u), format='json').status_code == 403
  assert client.post(b + 'status/', {'status': 'resolved'}, format='json').status_code == 403
  incident.refresh_from_db()
  assert incident.status == 'assigned'


def test_assigned_member_can_resolve_but_nothing_else(member_u, assigned_incident):
  client = client_for(member_u)
  b = base(assigned_incident)
  assert client.post(b + 'status/', {'status': 'in_progress'}, format='json').status_code == 403
  assert client.post(b + 'status/', {'status': 'closed'}, format='json').status_code == 403
  assert client.post(b + 'status/', {'status': 'resolved'}, format='json').status_code == 200
  assigned_incident.refresh_from_db()
  assert assigned_incident.status == 'resolved'


# ---- the incident's own leader and admins ------------------------------

def test_leader_assigns_a_member_of_their_team(as_leader, incident, member_u):
  res = as_leader.post(base(incident) + 'assign/', assign_body(member_u), format='json')
  assert res.status_code == 200
  incident.refresh_from_db()
  assert incident.status == 'assigned'
  assert ResponderAssignment.objects.filter(incident=incident).count() == 1


def test_admin_can_assign(as_admin, incident, member_u):
  res = as_admin.post(base(incident) + 'assign/', assign_body(member_u), format='json')
  assert res.status_code == 200


def test_leader_cannot_assign_a_member_of_another_team(as_leader, incident, other_member):
  res = as_leader.post(base(incident) + 'assign/', assign_body(other_member), format='json')
  assert res.status_code == 400
  assert not ResponderAssignment.objects.exists()


def test_leader_cannot_skip_steps_or_resolve(as_leader, incident):
  b = base(incident)
  assert as_leader.post(b + 'status/', {'status': 'in_progress'}, format='json').status_code == 400
  assert as_leader.post(b + 'status/', {'status': 'closed'}, format='json').status_code == 400
  assert as_leader.post(b + 'status/', {'status': 'resolved'}, format='json').status_code == 403
  incident.refresh_from_db()
  assert incident.status == 'submitted'


# ---- the shared permission class ---------------------------------------

def test_owner_permission_checks_the_reporter(incident, reporter_u, other_reporter):
  perm = IsOwnerOrAdmin()
  as_owner = type('Req', (), {'user': reporter_u})()
  as_stranger = type('Req', (), {'user': other_reporter})()
  assert perm.has_object_permission(as_owner, None, incident)
  assert not perm.has_object_permission(as_stranger, None, incident)
