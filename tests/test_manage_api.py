import pytest
from rest_framework.test import APIClient

from analytics.models import AuditLog
from teams.models import EmergencyCategory, ResponseTeam, TeamMember
from tests.helpers import NEW_PASSWORD, PASSWORD, client_for, make_user, rows
from users.models import User

pytestmark = pytest.mark.django_db

TEAM = {'team_name': 'Fire Unit', 'hotline_number': '+254 700 000 002', 'team_email': 'fire@example.com'}


def test_only_admins_can_use_the_manage_api(as_leader, as_reporter):
  for c in (as_leader, as_reporter):
    assert c.get('/api/manage/teams/').status_code == 403
    assert c.get('/api/manage/accounts/').status_code == 403
    assert c.get('/api/manage/categories/').status_code == 403
  assert APIClient().get('/api/manage/teams/').status_code == 401


# ---- teams -----------------------------------------------------------------

def test_admin_can_list_teams(as_admin, team):
  r = as_admin.get('/api/manage/teams/')
  assert r.status_code == 200, r.data
  assert [t['team_name'] for t in rows(r)] == ['Medical Unit']


def test_create_team_is_audited(as_admin, admin_u):
  r = as_admin.post('/api/manage/teams/', TEAM, format='json')
  assert r.status_code == 201, r.data
  assert r.data['leader'] is None
  assert AuditLog.objects.filter(user=admin_u, action='Created team').exists()


def test_team_names_are_unique_ignoring_case(as_admin, team):
  r = as_admin.post('/api/manage/teams/', dict(TEAM, team_name='medical unit'), format='json')
  assert r.status_code == 400 and 'team_name' in r.data


def test_team_phone_numbers_are_checked(as_admin):
  r = as_admin.post('/api/manage/teams/', dict(TEAM, hotline_number='call me'), format='json')
  assert r.status_code == 400 and 'hotline_number' in r.data


def test_a_new_team_cannot_start_with_a_leader(as_admin, leader_u):
  r = as_admin.post('/api/manage/teams/', dict(TEAM, leader=str(leader_u.id)), format='json')
  assert r.status_code == 400 and 'leader' in r.data


def test_leader_must_belong_to_the_team(as_admin, team):
  other_team = ResponseTeam.objects.create(
    team_name='Fire Unit', hotline_number='+254700000002', team_email='fire@example.com'
  )
  outsider = make_user('outsider@example.com', 'team_leader')
  TeamMember.objects.create(team=other_team, user=outsider)
  r = as_admin.patch(f'/api/manage/teams/{team.id}/', {'leader': str(outsider.id)}, format='json')
  assert r.status_code == 400 and 'leader' in r.data


def test_leader_must_have_the_leader_role(as_admin, team, member_u):
  r = as_admin.patch(f'/api/manage/teams/{team.id}/', {'leader': str(member_u.id)}, format='json')
  assert r.status_code == 400 and 'leader' in r.data


def test_leader_can_be_changed_to_another_leader_on_the_team(as_admin, team, leader_u):
  second = make_user('second@example.com', 'team_leader')
  TeamMember.objects.create(team=team, user=second)
  r = as_admin.patch(f'/api/manage/teams/{team.id}/', {'leader': str(second.id)}, format='json')
  assert r.status_code == 200, r.data
  team.refresh_from_db()
  assert team.leader_id == second.id


def test_an_idle_team_can_be_deactivated(as_admin, team):
  r = as_admin.patch(f'/api/manage/teams/{team.id}/', {'is_active': False}, format='json')
  assert r.status_code == 200, r.data
  team.refresh_from_db()
  assert team.is_active is False


# ---- categories -----------------------------------------------------------------

def test_category_names_are_unique_and_unused_ones_can_be_deleted(as_admin, team):
  r = as_admin.post('/api/manage/categories/', {'category_name': 'Medical Emergency', 'team': str(team.id)}, format='json')
  assert r.status_code == 201, r.data
  dup = as_admin.post('/api/manage/categories/', {'category_name': 'medical emergency', 'team': str(team.id)}, format='json')
  assert dup.status_code == 400
  assert as_admin.delete(f'/api/manage/categories/{r.data["id"]}/').status_code == 204
  assert not EmergencyCategory.objects.filter(category_name='Medical Emergency').exists()


def test_categories_cannot_be_given_to_a_deactivated_team(as_admin, team):
  team.is_active = False
  team.save()
  r = as_admin.post('/api/manage/categories/', {'category_name': 'Burns', 'team': str(team.id)}, format='json')
  assert r.status_code == 400 and 'team' in r.data


# ---- accounts ---------------------------------------------------------------------

def new_member(team, **extra):
  body = {'full_name': 'New Member', 'email': 'new@example.com', 'role': 'team_member', 'team': str(team.id)}
  body.update(extra)
  return body


def test_create_account_by_setup_link(as_admin, team, outbox):
  r = as_admin.post('/api/manage/accounts/', new_member(team), format='json')
  assert r.status_code == 201, r.data
  assert r.data['invite_sent'] is True
  user = User.objects.get(email='new@example.com')
  assert not user.has_usable_password()
  assert TeamMember.objects.filter(team=team, user=user).exists()
  assert outbox[-1]['to'] == 'new@example.com'
  assert 'reset-password?uid=' in outbox[-1]['text']


def test_create_account_with_a_temporary_password(as_admin, team):
  r = as_admin.post('/api/manage/accounts/', new_member(team, password=PASSWORD), format='json')
  assert r.status_code == 201, r.data
  user = User.objects.get(email='new@example.com')
  assert user.must_change_password is True
  assert user.check_password(PASSWORD)
  assert r.data['invite_sent'] is None


def test_temporary_passwords_must_pass_the_validators(as_admin, team):
  r = as_admin.post('/api/manage/accounts/', new_member(team, password='12345678'), format='json')
  assert r.status_code == 400 and 'password' in r.data


def test_staff_accounts_need_a_team(as_admin):
  r = as_admin.post('/api/manage/accounts/', {'full_name': 'No Team', 'email': 'nt@example.com', 'role': 'team_member'}, format='json')
  assert r.status_code == 400 and 'team' in r.data


def test_emails_are_unique_ignoring_case(as_admin, team, reporter_u):
  r = as_admin.post('/api/manage/accounts/', new_member(team, email='REPORTER@example.com'), format='json')
  assert r.status_code == 400 and 'email' in r.data


def test_reporter_accounts_cannot_be_created_here(as_admin):
  r = as_admin.post('/api/manage/accounts/', {'full_name': 'Rep', 'email': 'rep@example.com', 'role': 'general_user'}, format='json')
  assert r.status_code == 400 and 'role' in r.data


def test_accounts_can_be_filtered_by_role(as_admin, leader_u, member_u):
  r = as_admin.get('/api/manage/accounts/?role=team_leader')
  assert [a['email'] for a in rows(r)] == ['leader@example.com']


def test_a_team_leader_cannot_be_deactivated_or_demoted(as_admin, leader_u):
  for body in ({'is_active': False}, {'role': 'team_member'}):
    r = as_admin.patch(f'/api/manage/accounts/{leader_u.id}/', body, format='json')
    assert r.status_code == 400, body
    assert 'leader of' in str(r.data)
  leader_u.refresh_from_db()
  assert leader_u.is_active and leader_u.role == 'team_leader'


def test_a_member_can_be_moved_between_teams(as_admin, team, member_u):
  other = ResponseTeam.objects.create(team_name='Fire Unit', hotline_number='+254700000002', team_email='fire@example.com')
  r = as_admin.patch(f'/api/manage/accounts/{member_u.id}/', {'team': str(other.id)}, format='json')
  assert r.status_code == 200, r.data
  assert list(TeamMember.objects.filter(user=member_u).values_list('team_id', flat=True)) == [other.id]


def test_admins_cannot_demote_or_deactivate_themselves(as_admin, admin_u):
  for body in ({'role': 'team_member'}, {'is_active': False}):
    r = as_admin.patch(f'/api/manage/accounts/{admin_u.id}/', body, format='json')
    assert r.status_code == 400, body


def test_passwords_cannot_be_changed_through_edit(as_admin, member_u):
  r = as_admin.patch(f'/api/manage/accounts/{member_u.id}/', {'password': NEW_PASSWORD}, format='json')
  assert r.status_code == 400 and 'password' in r.data


# ---- resetting passwords -----------------------------------------------------------

def test_admin_reset_forces_a_change_signs_the_user_out_and_notifies(as_admin, admin_u, member_u, outbox):
  session = client_for(member_u)
  r = as_admin.post(f'/api/manage/accounts/{member_u.id}/reset-password/', {'password': NEW_PASSWORD}, format='json')
  assert r.status_code == 200, r.data
  assert r.data['notified'] is True
  member_u.refresh_from_db()
  assert member_u.must_change_password is True
  assert member_u.check_password(NEW_PASSWORD)
  assert session.get('/api/auth/me/').status_code == 401
  assert outbox[-1]['to'] == 'member@example.com'
  assert NEW_PASSWORD not in outbox[-1]['text']
  assert AuditLog.objects.filter(user=admin_u, action='Reset account password').exists()
  assert not AuditLog.objects.filter(entity_affected__contains=NEW_PASSWORD).exists()


def test_admins_cannot_reset_their_own_password_here(as_admin, admin_u):
  r = as_admin.post(f'/api/manage/accounts/{admin_u.id}/reset-password/', {'password': NEW_PASSWORD}, format='json')
  assert r.status_code == 400


def test_reset_passwords_must_pass_the_validators(as_admin, member_u):
  r = as_admin.post(f'/api/manage/accounts/{member_u.id}/reset-password/', {'password': '12345678'}, format='json')
  assert r.status_code == 400 and 'password' in r.data


def test_send_reset_link(as_admin, admin_u, member_u, outbox):
  r = as_admin.post(f'/api/manage/accounts/{member_u.id}/send-reset-link/')
  assert r.status_code == 200 and r.data['sent'] is True
  assert outbox[-1]['to'] == 'member@example.com'
  assert AuditLog.objects.filter(user=admin_u, action='Sent password reset link').exists()


def test_no_link_for_deactivated_accounts(as_admin, member_u):
  member_u.is_active = False
  member_u.save()
  assert as_admin.post(f'/api/manage/accounts/{member_u.id}/send-reset-link/').status_code == 400
