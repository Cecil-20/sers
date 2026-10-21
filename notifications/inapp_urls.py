from django.urls import path
from .inapp_views import (
    NotificationListView, UnreadCountView, MarkReadView, MarkAllReadView,
)

urlpatterns = [
    path('', NotificationListView.as_view()),
    path('unread-count/', UnreadCountView.as_view()),
    path('read-all/', MarkAllReadView.as_view()),
    path('<uuid:pk>/read/', MarkReadView.as_view()),
]
