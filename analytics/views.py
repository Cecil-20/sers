from rest_framework import generics, permissions
from rest_framework.views import APIView
from django.db.models import Count, Avg, F, Q, ExpressionWrapper, DurationField
from drf_spectacular.utils import extend_schema, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from incidents.models import Incident
from .models import AnalyticsReport
from .serializers import AnalyticsReportSerializer
from core.permissions import IsTeamLeaderOrAdmin
from .filters import filter_incidents
from rest_framework.response import Response

RESPONSE_TIME = ExpressionWrapper(
    F('resolved_at') - F('created_at'), output_field=DurationField()
)


def _seconds(delta):
    return delta.total_seconds() if delta else None


def incidents_in_scope(user):
    """Admins see every incident; a team leader sees only their own team's."""
    if user.role == 'general_admin':
        return Incident.objects.all(), None
    membership = user.team_memberships.select_related('team').first()
    if not membership:
        return Incident.objects.none(), None
    return Incident.objects.filter(team_id=membership.team_id), membership.team


class AnalyticsDashboardView(APIView):
    """Aggregate statistics, scoped to the caller: all teams for admins, the
    caller's own team for team leaders."""
    permission_classes = [permissions.IsAuthenticated, IsTeamLeaderOrAdmin]

    @extend_schema(
        description="Aggregate incident statistics scoped to the caller: all teams for "
                    "admins (with a per-team response time), the caller's own team for "
                    "team leaders. Includes hotline calls with their reference numbers.",
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Dashboard statistics",
                examples=None,
            )
        },
    )
    def get(self, request):
        user = request.user
        qs, own_team = incidents_in_scope(user)
        is_admin = user.role == 'general_admin'
        qs, _applied = filter_incidents(qs, request.query_params, is_admin)

        by_status = qs.values('status').annotate(count=Count('id')).order_by()
        by_category = (
            qs.values('category__category_name').annotate(count=Count('id')).order_by()
        )
        by_severity = qs.values('ai_severity').annotate(count=Count('id')).order_by()
        by_report_method = qs.values('report_method').annotate(count=Count('id')).order_by()

        team_rows = (
            qs.values('team_id', 'team__team_name')
            .annotate(
                total=Count('id'),
                resolved=Count('id', filter=Q(resolved_at__isnull=False)),
                avg_rt=Avg(RESPONSE_TIME, filter=Q(resolved_at__isnull=False)),
            )
            .order_by('team__team_name')
        )
        by_team = [
            {
                'team_id': str(row['team_id']) if row['team_id'] else None,
                'team_name': row['team__team_name'] or 'Unassigned',
                'total_incidents': row['total'],
                'resolved_incidents': row['resolved'],
                'average_response_time_seconds': _seconds(row['avg_rt']),
            }
            for row in team_rows
        ]

        # Admins deliberately get no single combined figure: each team's
        # response time is reported on its own row in by_team.
        if is_admin:
            average_response = None
        else:
            resolved = qs.filter(resolved_at__isnull=False).annotate(rt=RESPONSE_TIME)
            average_response = _seconds(resolved.aggregate(avg=Avg('rt'))['avg'])

        hotline_qs = qs.filter(report_method='hotline')
        hotline_calls = [
            {
                'reference_no': i.reference_no,
                'caller_number': i.caller_number,
                'team': i.team.team_name if i.team else None,
                'status': i.status,
                'created_at': i.created_at,
            }
            for i in hotline_qs.select_related('team').order_by('-created_at')[:50]
        ]

        return Response({
            'scope': 'all' if is_admin else 'team',
            'team_name': own_team.team_name if own_team else None,
            'total_incidents': qs.count(),
            'by_status': list(by_status),
            'by_category': list(by_category),
            'by_severity': list(by_severity),
            'by_report_method': list(by_report_method),
            'by_team': by_team,
            'average_response_time_seconds': average_response,
            'hotline_total': hotline_qs.count(),
            'hotline_calls': hotline_calls,
        })


class AnalyticsReportView(generics.ListCreateAPIView):
    """List existing generated reports, or trigger generation of a new one."""
    queryset = AnalyticsReport.objects.all().order_by('-generated_at')
    serializer_class = AnalyticsReportSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeamLeaderOrAdmin]

    def perform_create(self, serializer):
        serializer.save(generated_by=self.request.user)
