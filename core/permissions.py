from rest_framework.permissions import BasePermission

class IsGeneralAdmin(BasePermission):
	def has_permission(self, request, view):
		return bool (request.user and request.user.role == 'general_admin')

class IsTeamLeaderOrAdmin(BasePermission):
	def has_permission(self, request, view):
		return bool (request.user and request.user.role in ('general_admin', 'team_leader'))

class IsTeamMemberOfIncident(BasePermission):
	"""Allow access onlyto members of a team an incident is routed to"""
	def has_object_permission (self, request, view, obj):
		if request.user.role == 'general_admin':
			return True
		return obj.team.members.filter(user=request.user).exists()

class IsOwnerOrAdmin(BasePermission):
	"""Allows general user to access only their own submitted incidents"""
	def has_object_permission(self, request, view, obj):
		if request.user.role in ('general_admin', 'team_leader', 'team_member'):
			return True
		return obj.reporter_id == request.user.id
