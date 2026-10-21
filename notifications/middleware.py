from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from users.models import User


@database_sync_to_async
def get_user_from_token(token):
  """Same rules as the REST API: a valid access token, an active account, and
  a password unchanged since the token was issued."""
  try:
    access = AccessToken(token)
    user = User.objects.filter(pk=access[api_settings.USER_ID_CLAIM], is_active=True).first()
    if user is None:
      return AnonymousUser()
    if api_settings.CHECK_REVOKE_TOKEN:
      claim = api_settings.REVOKE_TOKEN_CLAIM
      if access.get(claim) != RefreshToken.for_user(user)[claim]:
        return AnonymousUser()
    return user
  except Exception as e:
    # Log the kind of failure only, never the token.
    print('WebSocket auth refused:', type(e).__name__)
    return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
  async def __call__(self, scope, receive, send):
    query = parse_qs(scope['query_string'].decode())
    token = (query.get('token') or [None])[0]
    scope['user'] = await get_user_from_token(token) if token else AnonymousUser()
    return await super().__call__(scope, receive, send)
