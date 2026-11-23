from core.health import health
import core.schema  # noqa: F401  (registers the API-docs auth scheme)
from django.conf import settings
from core.login import ThrottledLoginView
from core.token_views import CheckedTokenRefreshView
from users.register import RegisterView
"""
URL configuration for sers_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView,)
from users.views import CurrentUserView

urlpatterns = [
    path('healthz/', health),
    path(settings.ADMIN_URL, admin.site.urls),
    path('api/auth/login/',	ThrottledLoginView.as_view()),
    path('api/auth/refresh/',	CheckedTokenRefreshView.as_view()),
    path('api/auth/me/',	CurrentUserView.as_view()),
    path('api/auth/register/', RegisterView.as_view()),
    path('api/hotline/', include('incidents.hotline_urls')),
    path('api/notifications/', include('notifications.inapp_urls')),
    path('api/ai/', include('ai_module.urls')),
    path('api/incident-actions/', include('incidents.action_urls')),
    path('api/manage/', include('core.manage_urls')),
    path('api/account/', include('core.account_urls')),
    path('api/users/',		include('users.urls')),
    path('api/teams/',		include('teams.urls')),
    path('api/incidents/',	include('incidents.urls')),
    path('api/analytics/',	include('analytics.urls')),
    path('api/schema/',		SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/',		SpectacularSwaggerView.as_view(url_name='schema')),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
