from django.contrib import admin
from .models import AnalyticsReport, AuditLog


@admin.register(AnalyticsReport)
class AnalyticsReportAdmin(admin.ModelAdmin):
    list_display = (
        'report_type',
        'generated_by',
        'date_range_start',
        'date_range_end',
        'generated_at'
    )
    search_fields = ('report_type', 'generated_by__username')
    list_filter = ('report_type', 'generated_at')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'action',
        'entity_affected',
        'timestamp'
    )
    search_fields = ('action', 'entity_affected', 'user__username')
    list_filter = ('timestamp',)
