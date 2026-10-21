from django.shortcuts import render
from rest_framework import viewsets, permissions
from .models import ResponseTeam, EmergencyCategory
from .serializers import ResponseTeamSerializer, EmergencyCategorySerializer
from core.permissions import IsGeneralAdmin

# Create your views here.
class ResponseTeamViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = ResponseTeam.objects.all()
	serializer_class = ResponseTeamSerializer

	def get_permissions(self):
		if self.action in ['create', 'update', 'partial_update', 'destroy']:
			return [permissions.IsAuthenticated(), IsGeneralAdmin()]
		return [permissions.IsAuthenticated()]

class EmergencyCategoryViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = EmergencyCategory.objects.all()
	serializer_class = EmergencyCategorySerializer

	def get_permissions(self):
		if self.action in ['create', 'update', 'partial_update', 'destroy']:
			return [permissions.IsAuthenticated(), IsGeneralAdmin()]
		return [permissions.IsAuthenticated()]
