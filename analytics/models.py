import uuid
from django.db import models
from users.models import User

# Create your models here.
class AnalyticsReport(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null= True)
	report_type = models.CharField(max_length=50)
	date_range_start = models.DateField()
	date_range_end = models.DateField()
	file_url = models.URLField(blank=True)
	file_name = models.CharField(max_length=120, blank=True)
	filters = models.JSONField(default=dict, blank=True)
	pdf_data = models.BinaryField(null=True, blank=True, editable=False)
	generated_at = models.DateTimeField(auto_now_add=True)

class AuditLog(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	user = models.ForeignKey(User, on_delete=models.SET_NULL,null=True)
	action = models.CharField(max_length=150)
	entity_affected = models.CharField(max_length=100)
	timestamp = models.DateTimeField(auto_now_add=True)
