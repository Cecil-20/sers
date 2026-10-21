import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

LEGACY = ['/api/teams/response-teams/', '/api/teams/categories/']


@pytest.mark.parametrize('url', LEGACY)
def test_the_old_routes_are_read_only_even_for_admins(as_admin, team, url):
  assert as_admin.post(url, {}, format='json').status_code == 405
  detail = f'{url}{team.id}/'
  assert as_admin.patch(detail, {}, format='json').status_code in (404, 405)
  assert as_admin.put(detail, {}, format='json').status_code in (404, 405)
  assert as_admin.delete(detail).status_code in (404, 405)


def test_reporters_can_still_read_categories(as_reporter, team):
  assert as_reporter.get('/api/teams/categories/').status_code == 200


def test_the_old_routes_still_need_a_login():
  assert APIClient().get('/api/teams/categories/').status_code == 401
