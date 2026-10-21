import uuid

import cloudinary.uploader
import pytest
from django.core.files.base import ContentFile
from rest_framework.test import APIClient

from core.private_storage import PrivateMediaCloudinaryStorage
from incidents.models import IncidentImage
from tests.factories import make_category, make_incident
from tests.helpers import client_for, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fake_signing(monkeypatch):
  monkeypatch.setattr(
    PrivateMediaCloudinaryStorage, 'signed_url',
    lambda self, name, seconds=300: f'https://signed.test/{name}',
  )


@pytest.fixture
def photo(team, reporter_u):
  incident = make_incident(reporter_u, make_category(team))
  image = IncidentImage.objects.create(incident=incident, image='incident_images/abc')
  return incident, image


def photo_url(incident, image):
  return f'/api/incidents/{incident.pk}/photos/{image.pk}/'


def test_reporter_gets_signed_url(photo, as_reporter):
  res = as_reporter.get(photo_url(*photo))
  assert res.status_code == 200
  assert res.data['url'] == 'https://signed.test/incident_images/abc'
  assert res['Cache-Control'] == 'no-store'


def test_team_leader_of_the_team_gets_it(photo, as_leader):
  assert as_leader.get(photo_url(*photo)).status_code == 200


def test_admin_gets_it(photo, as_admin):
  assert as_admin.get(photo_url(*photo)).status_code == 200


def test_other_reporter_is_refused(photo):
  other = make_user('someone.else@example.com')
  assert client_for(other).get(photo_url(*photo)).status_code == 404


def test_leader_of_another_team_is_refused(photo):
  other = make_user('other.leader@example.com', role='team_leader')
  assert client_for(other).get(photo_url(*photo)).status_code == 404


def test_anonymous_is_refused(photo):
  assert APIClient().get(photo_url(*photo)).status_code == 401


def test_unknown_or_malformed_image_id_is_404(photo, as_reporter):
  incident, _ = photo
  assert as_reporter.get(f'/api/incidents/{incident.pk}/photos/{uuid.uuid4()}/').status_code == 404
  assert as_reporter.get(f'/api/incidents/{incident.pk}/photos/not-a-uuid/').status_code == 404


def test_incident_payload_has_no_raw_image_url(photo, as_reporter):
  incident, _ = photo
  res = as_reporter.get(f'/api/incidents/{incident.pk}/')
  assert res.status_code == 200
  assert res.data['images'] and 'image' not in res.data['images'][0]


def test_uploads_are_authenticated(monkeypatch):
  seen = {}

  def fake_upload(content, **options):
    seen.update(options)
    return {'public_id': 'incident_images/p_abc'}

  monkeypatch.setattr(cloudinary.uploader, 'upload', fake_upload)
  name = PrivateMediaCloudinaryStorage()._save('incident_images/p.jpg', ContentFile(b'x'))
  assert name == 'incident_images/p_abc'
  assert seen['type'] == 'authenticated'
