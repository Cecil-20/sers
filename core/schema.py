from drf_spectacular.extensions import OpenApiAuthenticationExtension


class PasswordChangeJWTScheme(OpenApiAuthenticationExtension):
  """Tell the API docs our custom auth class is ordinary Bearer-token JWT."""
  target_class = 'core.authentication.PasswordChangeJWTAuthentication'
  name = 'jwtAuth'

  def get_security_definition(self, auto_schema):
    return {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'}
