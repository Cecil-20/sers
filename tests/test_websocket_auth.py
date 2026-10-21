import pytest
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from notifications.consumers import IncidentConsumer
from notifications.middleware import JWTAuthMiddleware
from tests.helpers import NEW_PASSWORD, token_for
from users.models import User

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]

APP = JWTAuthMiddleware(IncidentConsumer.as_asgi())


def talker(token=None):
  path = '/ws/incidents/' + (f'?token={token}' if token else '')
  return WebsocketCommunicator(APP, path)


async def connects(token=None):
  comm = talker(token)
  connected, _ = await comm.connect()
  if connected:
    await comm.disconnect()
  return connected


async def test_a_valid_token_connects(reporter_u):
  assert await connects(token_for(reporter_u)) is True


async def test_missing_and_garbage_tokens_are_refused():
  assert await connects() is False
  assert await connects('not.a.token') is False


async def test_a_token_is_refused_after_the_password_changes(reporter_u):
  token = token_for(reporter_u)

  def change():
    reporter_u.set_password(NEW_PASSWORD)
    reporter_u.save()

  await sync_to_async(change)()
  assert await connects(token) is False


async def test_deactivated_accounts_are_refused(reporter_u):
  token = token_for(reporter_u)
  await sync_to_async(User.objects.filter(pk=reporter_u.pk).update)(is_active=False)
  assert await connects(token) is False


async def test_an_open_socket_closes_when_told_to(reporter_u):
  comm = talker(token_for(reporter_u))
  connected, _ = await comm.connect()
  assert connected
  await get_channel_layer().group_send(f'user_{reporter_u.pk}', {'type': 'force_logout'})
  output = await comm.receive_output(timeout=2)
  assert output['type'] == 'websocket.close'
  await comm.disconnect()
