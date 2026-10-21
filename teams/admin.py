from django.contrib import admin
from .models import ResponseTeam, TeamMember, EmergencyCategory

# Register your models here.
@admin.register(ResponseTeam)
class ResponseTeamAdmin(admin.ModelAdmin):
	list_display = ('team_name', 'leader', 'hotline_number', 'team_email', 'is_active')
	search_fields = ('team_name', 'team_email')

admin.site.register(TeamMember)
admin.site.register(EmergencyCategory)
