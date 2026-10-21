from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView


class CheckedRefreshSerializer(TokenRefreshSerializer):
  """Refuse a refresh token that is stale: password changed, or account off."""

  def validate(self, attrs):
    try:
      token = RefreshToken(attrs['refresh'])
    except TokenError as exc:
      raise InvalidToken(exc.args[0])
    user = get_user_model().objects.filter(
      pk=token.get(api_settings.USER_ID_CLAIM), is_active=True
    ).first()
    if user is None:
      raise InvalidToken('User not found or inactive.')
    claim = api_settings.REVOKE_TOKEN_CLAIM
    if token.get(claim) != RefreshToken.for_user(user)[claim]:
      raise InvalidToken('The password has changed. Please sign in again.')
    return super().validate(attrs)


class CheckedTokenRefreshView(TokenRefreshView):
  serializer_class = CheckedRefreshSerializer
