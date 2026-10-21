from rest_framework import serializers
from .models import AnalyticsReport


class AnalyticsReportSerializer(serializers.ModelSerializer):
  generated_by_email = serializers.EmailField(
    source='generated_by.email', read_only=True, default=None
  )

  class Meta:
    model = AnalyticsReport
    fields = [
      'id', 'generated_by', 'generated_by_email', 'report_type',
      'date_range_start', 'date_range_end', 'filters', 'file_name',
      'file_url', 'generated_at',
    ]
    read_only_fields = fields
