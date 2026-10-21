import re

import pytest
from rest_framework.test import APIClient

from tests.helpers import NEW_PASSWORD, PASSWORD, client_for, make_user

pytestmark = pytest.mark.django_db

LINK = re.compile(r'uid=([^&\s]+)&token=([^\s]+)')


def forgot(email):
  return APIClient().post('/api/account/forgot-password/', {'email': email}, format='json')


def confirm(uid, token, password=NEW_PASSWORD):
  body = {'uid': uid, 'token': token, 'new_password': password}
  return APIClient().post('/api/account/reset-password/', body, format='json')


def link_from(outbox):
  match = LINK.search(outbox[-1]['text'])
  assert match, 'no reset link in the email'
  return match.group(1), match.group(2)


def test_unknown_emails_get_the_same_answer_and_no_email(outbox, reporter_u):
  known = forgot('reporter@example.com')
  outbox.clear()
  unknown = forgot('nobody@example.com')
  assert unknown.status_code == known.status_code == 200
  assert unknown.data == known.data
  assert outbox == []


def test_a_known_email_gets_a_link(outbox, reporter_u):
  assert forgot('reporter@example.com').status_code == 200
  assert len(outbox) == 1
  assert outbox[0]['to'] == 'reporter@example.com'
  assert 'reset' in outbox[0]['subject'].lower()


def test_deactivated_accounts_get_no_email(outbox):
  make_user('off@example.com', is_active=False)
  forgot('off@example.com')
  assert outbox == []


def test_the_link_sets_a_new_password_once(outbox, reporter_u):
  reporter_u.must_change_password = True
  reporter_u.save()
  forgot('reporter@example.com')
  uid, token = link_from(outbox)
  assert confirm(uid, token).status_code == 200
  reporter_u.refresh_from_db()
  assert reporter_u.must_change_password is False
  login = APIClient().post('/api/auth/login/', {'email': 'reporter@example.com', 'password': NEW_PASSWORD}, format='json')
  assert login.status_code == 200
  assert confirm(uid, token, 'Y3t-Another-Pass-77').status_code == 400


def test_using_the_link_signs_out_existing_sessions(outbox, reporter_u):
  old_session = client_for(reporter_u)
  forgot('reporter@example.com')
  uid, token = link_from(outbox)
  confirm(uid, token)
  assert old_session.get('/api/auth/me/').status_code == 401


def test_weak_passwords_are_refused_and_the_link_survives(outbox, reporter_u):
  forgot('reporter@example.com')
  uid, token = link_from(outbox)
  weak = confirm(uid, token, '12345678')
  assert weak.status_code == 400 and 'new_password' in weak.data
  assert confirm(uid, token).status_code == 200


def test_bad_links_are_refused(outbox, reporter_u):
  forgot('reporter@example.com')
  uid, token = link_from(outbox)
  assert confirm(uid, 'not-a-real-token').status_code == 400
  assert confirm('garbage', token).status_code == 400
  assert confirm('', '').status_code == 400


def test_expired_links_are_refused(outbox, reporter_u, settings):
  settings.PASSWORD_RESET_TIMEOUT = -1
  forgot('reporter@example.com')
  uid, token = link_from(outbox)
  assert confirm(uid, token).status_code == 400


def test_a_stale_token_in_the_browser_does_not_block_the_public_endpoints(outbox, reporter_u):
  c = APIClient()
  c.credentials(HTTP_AUTHORIZATION='Bearer this.is.not.valid')
  assert c.post('/api/account/forgot-password/', {'email': 'reporter@example.com'}, format='json').status_code == 200


def test_forgot_password_is_rate_limited(reporter_u):
  codes = [forgot('reporter@example.com').status_code for _ in range(11)]
  assert codes[:10] == [200] * 10
  assert codes[10] == 429
