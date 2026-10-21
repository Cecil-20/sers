from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def disconnect_user(user):
  """Close every open alert socket this user has. The browser reconnects with
  its current token, so a revoked or re-scoped user simply stays out. Never raises."""
  try:
    layer = get_channel_layer()
    if layer is not None:
      async_to_sync(layer.group_send)(f'user_{user.pk}', {'type': 'force_logout'})
  except Exception as e:
    print('Could not disconnect sockets:', type(e).__name__)
