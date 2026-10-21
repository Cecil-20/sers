import pytest
from rest_framework.test import APIClient

from analytics.models import AuditLog
from tests.helpers import PASSWORD

pytestmark = pytest.mark.django_db

DELETE = {'password': PASSWORD, 'confirm': 'DELETE'}


def test_profile_can_be_read_and_edited(as_reporter):
  assert as_reporter.get('/api/account/profile/').data['email'] == 'reporter@example.com'
  r = as_reporter.patch('/api/account/profile/', {'full_name': 'Jane Doe', 'phone_number': '+254 700 000 000'}, format='json')
  assert r.status_code == 200, r.data
  assert r.data['full_name'] == 'Jane Doe'


@pytest.mark.parametrize('body,field', [
  ({'phone_number': 'call me'}, 'phone_number'),
  ({'full_name': 'J'}, 'full_name'),
])
def test_profile_validation(as_reporter, body, field):
  r = as_reporter.patch('/api/account/profile/', body, format='json')
  assert r.status_code == 400 and field in r.data


def test_the_email_cannot_be_changed_from_the_profile(as_reporter, reporter_u):
  as_reporter.patch('/api/account/profile/', {'email': 'other@example.com'}, format='json')
  reporter_u.refresh_from_db()
  assert reporter_u.email == 'reporter@example.com'


def test_data_export_is_a_json_download(as_reporter):
  r = as_reporter.get('/api/account/export/')
  assert r.status_code == 200, r.data
  assert 'attachment' in r['Content-Disposition']
  assert set(r.data) >= {'exported_at', 'profile', 'incidents_reported'}
  assert r.data['incidents_reported'] == []


def test_the_account_endpoints_need_a_login():
  c = APIClient()
  for path in ('/api/account/profile/', '/api/account/export/'):
    assert c.get(path).status_code == 401
  assert c.post('/api/account/delete/', DELETE, format='json').status_code == 401


def test_deleting_an_account_anonymises_it_and_signs_out(as_reporter, reporter_u):
  r = as_reporter.post('/api/account/delete/', DELETE, format='json')
  assert r.status_code == 200, r.data
  reporter_u.refresh_from_db()
  assert reporter_u.full_name == 'Deleted user'
  assert reporter_u.email.endswith('@deleted.invalid')
  assert reporter_u.phone_number == ''
  assert reporter_u.is_active is False
  assert not reporter_u.has_usable_password()
  assert as_reporter.get('/api/auth/me/').status_code == 401
  login = APIClient().post('/api/auth/login/', {'email': 'reporter@example.com', 'password': PASSWORD}, format='json')
  assert login.status_code == 401
  assert AuditLog.objects.filter(action='Deleted own account').exists()


def test_deleting_needs_the_password_and_the_typed_word(as_reporter, reporter_u):
  wrong = as_reporter.post('/api/account/delete/', {'password': 'nope-nope-1', 'confirm': 'DELETE'}, format='json')
  assert wrong.status_code == 400 and 'password' in wrong.data
  no_word = as_reporter.post('/api/account/delete/', {'password': PASSWORD, 'confirm': 'delete me'}, format='json')
  assert no_word.status_code == 400 and 'confirm' in no_word.data
  reporter_u.refresh_from_db()
  assert reporter_u.is_active


def test_staff_cannot_delete_their_own_accounts(as_leader, as_admin, leader_u):
  assert as_leader.post('/api/account/delete/', DELETE, format='json').status_code == 403
  assert as_admin.post('/api/account/delete/', DELETE, format='json').status_code == 403
  leader_u.refresh_from_db()
  assert leader_u.is_active
