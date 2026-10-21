import pytest
from channels.testing import WebsocketCommunicator
from django.conf import settings

from sers_backend.asgi import application
from tests.helpers import token_for

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


async def connects(token, origin):
  headers = [(b'origin', origin.encode())] if origin else []
  comm = WebsocketCommunicator(application, f'/ws/incidents/?token={token}', headers=headers)
  connected, _ = await comm.connect()
  if connected:
    await comm.disconnect()
  return connected


async def test_a_listed_origin_connects(reporter_u):
  origin = settings.CORS_ALLOWED_ORIGINS[0]
  assert await connects(token_for(reporter_u), origin) is True


async def test_another_site_is_refused_even_with_a_valid_token(reporter_u):
  assert await connects(token_for(reporter_u), 'https://evil.example') is False


async def test_a_missing_origin_is_refused(reporter_u):
  assert await connects(token_for(reporter_u), None) is False
