import logging

import pytest
from rest_framework.test import APIClient

from tests.helpers import PASSWORD, make_user

pytestmark = pytest.mark.django_db


def attempt(email, password='wrong-password-1'):
  return APIClient().post('/api/auth/login/', {'email': email, 'password': password}, format='json')


def test_repeated_guesses_at_one_account_are_throttled(reporter_u):
  codes = [attempt('reporter@example.com').status_code for _ in range(6)]
  assert codes[:5] == [401] * 5
  assert codes[5] == 429


def test_the_lockout_also_blocks_the_right_password(reporter_u):
  for _ in range(5):
    attempt('reporter@example.com')
  assert attempt('reporter@example.com', PASSWORD).status_code == 429


def test_other_accounts_are_not_affected(reporter_u):
  make_user('other@example.com')
  for _ in range(5):
    attempt('reporter@example.com')
  assert attempt('other@example.com', PASSWORD).status_code == 200


def test_one_address_cannot_spray_many_accounts():
  codes = [attempt(f'user{i}@example.com').status_code for i in range(31)]
  assert codes[:30] == [401] * 30
  assert codes[30] == 429


def test_failed_logins_are_logged(reporter_u, caplog):
  with caplog.at_level(logging.WARNING, logger='serims.security'):
    attempt('reporter@example.com')
  assert 'login_failed' in caplog.text
  assert 'reporter@example.com' in caplog.text


def test_good_logins_are_not_logged_as_failures(reporter_u, caplog):
  with caplog.at_level(logging.WARNING, logger='serims.security'):
    assert attempt('reporter@example.com', PASSWORD).status_code == 200
  assert 'login_failed' not in caplog.text
