import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sers_backend.settings')

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator
from django.conf import settings
import notifications.routing
from notifications.middleware import JWTAuthMiddleware

# The browser's Origin is the frontend's address, not this server's, so the
# check uses the same list as CORS rather than ALLOWED_HOSTS.
application = ProtocolTypeRouter({
  'http': django_asgi_app,
  'websocket': OriginValidator(
    JWTAuthMiddleware(
      URLRouter(notifications.routing.websocket_urlpatterns)
    ),
    settings.CORS_ALLOWED_ORIGINS,
  ),
})
