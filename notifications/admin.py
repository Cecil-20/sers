from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'incident',
        'channel',
        'recipient',
        'delivery_status',
        'sent_at'
    )
    search_fields = (
        'recipient',
        'incident__title'
    )
    list_filter = (
        'channel',
        'delivery_status',
        'sent_at'
    )
