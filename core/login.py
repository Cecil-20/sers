import hashlib
import logging

from rest_framework.exceptions import AuthenticationFailed
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView

log = logging.getLogger('serims.security')


class LoginIPThrottle(AnonRateThrottle):
  """One address spraying many accounts."""
  scope = 'login_ip'
  rate = '30/min'


class LoginEmailThrottle(SimpleRateThrottle):
  """Many addresses hammering one account."""
  scope = 'login_email'
  rate = '5/min'

  def get_cache_key(self, request, view):
    email = str(request.data.get('email', '')).strip().lower()
    if not email:
      return None
    digest = hashlib.sha256(email.encode()).hexdigest()
    return self.cache_format % {'scope': self.scope, 'ident': digest}


class ThrottledLoginView(TokenObtainPairView):
  throttle_classes = [LoginIPThrottle, LoginEmailThrottle]

  def post(self, request, *args, **kwargs):
    try:
      return super().post(request, *args, **kwargs)
    except (AuthenticationFailed, InvalidToken, TokenError):
      email = str(request.data.get('email', '')).strip().lower()[:100]
      log.warning('login_failed ip=%s email=%s', request.META.get('REMOTE_ADDR'), email)
      raise
