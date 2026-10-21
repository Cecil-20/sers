import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sers_backend.settings')

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
import notifications.routing
from notifications.middleware import JWTAuthMiddleware

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        JWTAuthMiddleware(
            URLRouter(notifications.routing.websocket_urlpatterns)
        )
    ),
})
