from rest_framework import serializers
from .models import ResponseTeam, TeamMember, EmergencyCategory

class EmergencyCategorySerializer(serializers.ModelSerializer):
	class Meta:
		model = EmergencyCategory
		fields = ['id', 'category_name', 'team', 'is_custom']

class ResponseTeamSerializer (serializers.ModelSerializer):
	categories = EmergencyCategorySerializer(many=True, read_only=True)
	class Meta:
		model = ResponseTeam
		fields = ['id', 'team_name', 'leader', 'hotline_number', 'team_email', 'is_active', 'categories', 'created_at']
