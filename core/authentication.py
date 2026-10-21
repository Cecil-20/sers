from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication

# Everything a user with a temporary password is still allowed to call.
ALLOWED_PATHS = ('/api/auth/me/', '/api/account/change-password/')


class PasswordChangeJWTAuthentication(JWTAuthentication):
  def authenticate(self, request):
    result = super().authenticate(request)
    if result is None:
      return None
    user = result[0]
    if getattr(user, 'must_change_password', False) and request.path not in ALLOWED_PATHS:
      raise exceptions.PermissionDenied({
        'detail': 'You must change your temporary password before continuing.',
        'code': 'password_change_required',
      })
    return result
