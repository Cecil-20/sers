from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from teams.models import EmergencyCategory, ResponseTeam
from .models import Incident
from .pipeline import finalize_new_incident


class HotlineNumbersView(APIView):
    """Hotline number of every active response team (shown to reporters)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        teams = (
            ResponseTeam.objects.filter(is_active=True)
            .order_by('team_name')
            .values('id', 'team_name', 'hotline_number')
        )
        return Response(list(teams))


class HotlineCallSerializer(serializers.Serializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=EmergencyCategory.objects.select_related('team')
    )
    caller_number = serializers.RegexField(
        r'^\+?[0-9 ()\-]{7,20}$',
        max_length=20,
        error_messages={'invalid': 'Enter a valid phone number.'},
    )
    description = serializers.CharField()
    custom_type_text = serializers.CharField(max_length=150, required=False, allow_blank=True)
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )


class HotlineCallView(APIView):
    """An operator logs a call that came in on the hotline."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.role not in ('general_admin', 'team_leader'):
            return Response(
                {'detail': 'Only administrators and team leaders can log hotline calls.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = HotlineCallSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        category = data['category']

        if user.role == 'team_leader':
            membership = user.team_memberships.first()
            if not membership or membership.team_id != category.team_id:
                return Response(
                    {'detail': "Team leaders can only log calls for their own team's categories."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        incident = Incident.objects.create(
            reporter=user,
            category=category,
            team=category.team,
            report_method='hotline',
            description=data['description'],
            custom_type_text=data.get('custom_type_text', ''),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            caller_number=data['caller_number'],
        )
        finalize_new_incident(incident)

        return Response(
            {
                'id': str(incident.id),
                'reference_no': incident.reference_no,
                'status': incident.status,
                'caller_number': incident.caller_number,
                'team': category.team.team_name,
                'ai_severity': incident.ai_severity,
            },
            status=status.HTTP_201_CREATED,
        )
