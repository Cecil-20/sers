import pytest
from rest_framework.test import APIClient

from tests.helpers import NEW_PASSWORD, PASSWORD, client_for, make_user

pytestmark = pytest.mark.django_db


def login(email, password):
  return APIClient().post('/api/auth/login/', {'email': email, 'password': password}, format='json')


def test_login_returns_tokens(reporter_u):
  r = login('reporter@example.com', PASSWORD)
  assert r.status_code == 200
  assert 'access' in r.data and 'refresh' in r.data


def test_login_rejects_a_wrong_password(reporter_u):
  assert login('reporter@example.com', 'wrong-password-1').status_code == 401


def test_deactivated_accounts_cannot_log_in():
  make_user('off@example.com', is_active=False)
  assert login('off@example.com', PASSWORD).status_code == 401


def test_temporary_password_blocks_the_api_but_not_me_or_change_password():
  user = make_user('tmp@example.com', 'general_admin', must_change_password=True)
  c = client_for(user)
  blocked = c.get('/api/manage/teams/')
  assert blocked.status_code == 403
  assert blocked.data['code'] == 'password_change_required'
  me = c.get('/api/auth/me/')
  assert me.status_code == 200
  assert me.data['must_change_password'] is True


def test_changing_password_clears_the_flag_and_keeps_the_session_alive():
  user = make_user('tmp@example.com', must_change_password=True)
  r = client_for(user).post(
    '/api/account/change-password/',
    {'current_password': PASSWORD, 'new_password': NEW_PASSWORD},
    format='json',
  )
  assert r.status_code == 200
  user.refresh_from_db()
  assert user.must_change_password is False
  fresh = APIClient()
  fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
  assert fresh.get('/api/auth/me/').status_code == 200
  assert login('tmp@example.com', NEW_PASSWORD).status_code == 200


def test_changing_password_revokes_every_other_session(reporter_u):
  old_session = client_for(reporter_u)
  r = client_for(reporter_u).post(
    '/api/account/change-password/',
    {'current_password': PASSWORD, 'new_password': NEW_PASSWORD},
    format='json',
  )
  assert r.status_code == 200
  assert old_session.get('/api/auth/me/').status_code == 401


def test_old_refresh_tokens_stop_working_after_a_password_change(reporter_u):
  refresh = login('reporter@example.com', PASSWORD).data['refresh']
  client_for(reporter_u).post(
    '/api/account/change-password/',
    {'current_password': PASSWORD, 'new_password': NEW_PASSWORD},
    format='json',
  )
  r = APIClient().post('/api/auth/refresh/', {'refresh': refresh}, format='json')
  assert r.status_code in (400, 401)


@pytest.mark.parametrize('payload,field', [
  ({'current_password': 'not-my-password-1', 'new_password': NEW_PASSWORD}, 'current_password'),
  ({'current_password': PASSWORD, 'new_password': PASSWORD}, 'new_password'),
  ({'current_password': PASSWORD, 'new_password': '12345678'}, 'new_password'),
])
def test_change_password_validation(as_reporter, payload, field):
  r = as_reporter.post('/api/account/change-password/', payload, format='json')
  assert r.status_code == 400
  assert field in r.data


def test_change_password_is_rate_limited(as_reporter):
  bad = {'current_password': 'not-my-password-1', 'new_password': NEW_PASSWORD}
  codes = [as_reporter.post('/api/account/change-password/', bad, format='json').status_code for _ in range(11)]
  assert codes[-1] == 429


def test_new_accounts_must_accept_the_terms_once(reporter_u, as_reporter):
  assert as_reporter.get('/api/auth/me/').data['needs_terms'] is True
  assert as_reporter.post('/api/account/accept-terms/').status_code == 200
  assert as_reporter.get('/api/auth/me/').data['needs_terms'] is False
  reporter_u.refresh_from_db()
  assert reporter_u.accepted_terms_at is not None
