from collections import Counter
from datetime import date

from django.db.models import Max, Min
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsTeamLeaderOrAdmin
from .filters import filter_incidents
from .models import AnalyticsReport
from .pdf import build_report_pdf
from .serializers import AnalyticsReportSerializer
from .views import incidents_in_scope

SEVERITY_RANK = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
SEVERITY_BY_RANK = {rank: name for name, rank in SEVERITY_RANK.items()}
CELL_DECIMALS = 3
MAX_POINTS = 5000
GUARDS = [permissions.IsAuthenticated, IsTeamLeaderOrAdmin]


def _reports_for(user):
  qs = AnalyticsReport.objects.select_related('generated_by')
  if user.role != 'general_admin':
    qs = qs.filter(generated_by=user)
  return qs


def _date_range(qs, applied):
  today = timezone.localdate()
  bounds = qs.aggregate(first=Min('created_at'), last=Max('created_at'))
  first = timezone.localtime(bounds['first']).date() if bounds['first'] else today
  last = timezone.localtime(bounds['last']).date() if bounds['last'] else today
  start = date.fromisoformat(applied['date_from']) if 'date_from' in applied else first
  end = date.fromisoformat(applied['date_to']) if 'date_to' in applied else last
  return start, end


class ReportListView(generics.ListAPIView):
  """Previously generated reports: all for admins, your own for leaders."""
  serializer_class = AnalyticsReportSerializer
  permission_classes = GUARDS

  def get_queryset(self):
    return _reports_for(self.request.user).defer('pdf_data').order_by('-generated_at')


class GenerateReportView(APIView):
  """Build a PDF for the current scope and filters, store it, return its record."""
  permission_classes = GUARDS

  def post(self, request):
    user = request.user
    qs, own_team = incidents_in_scope(user)
    qs, applied = filter_incidents(qs, request.data, user.role == 'general_admin')
    pdf_bytes = build_report_pdf(qs, user, own_team, applied)
    start, end = _date_range(qs, applied)
    stamp = timezone.localtime().strftime('%Y%m%d-%H%M%S')
    report = AnalyticsReport.objects.create(
      generated_by=user,
      report_type='incident_summary',
      date_range_start=start,
      date_range_end=end,
      filters=applied,
      pdf_data=pdf_bytes,
      file_name=f'serims-report-{stamp}.pdf',
    )
    url = reverse('analytics-report-download', args=[report.pk])
    report.file_url = request.build_absolute_uri(url)
    report.save(update_fields=['file_url'])
    return Response(AnalyticsReportSerializer(report).data, status=status.HTTP_201_CREATED)


class ReportDownloadView(APIView):
  """Stream a stored PDF. Admins can fetch any; leaders only their own."""
  permission_classes = GUARDS

  def get(self, request, pk):
    report = get_object_or_404(_reports_for(request.user), pk=pk)
    if not report.pdf_data:
      raise Http404
    response = HttpResponse(bytes(report.pdf_data), content_type='application/pdf')
    name = report.file_name or 'serims-report.pdf'
    response['Content-Disposition'] = f'attachment; filename="{name}"'
    return response


def _summarise(cells):
  result = []
  for cell in cells.values():
    count = len(cell['lats'])
    result.append({
      'latitude': sum(cell['lats']) / count,
      'longitude': sum(cell['lngs']) / count,
      'count': count,
      'top_category': cell['categories'].most_common(1)[0][0],
      'max_severity': SEVERITY_BY_RANK.get(cell['rank']),
    })
  result.sort(key=lambda r: r['count'], reverse=True)
  return result[:200]


def _cluster(rows):
  cells = {}
  for lat, lng, category, severity in rows:
    lat, lng = float(lat), float(lng)
    key = (round(lat, CELL_DECIMALS), round(lng, CELL_DECIMALS))
    cell = cells.setdefault(key, {'lats': [], 'lngs': [], 'categories': Counter(), 'rank': 0})
    cell['lats'].append(lat)
    cell['lngs'].append(lng)
    cell['categories'][category or 'Uncategorized'] += 1
    cell['rank'] = max(cell['rank'], SEVERITY_RANK.get(severity, 0))
  return _summarise(cells)


class HotspotsView(APIView):
  """Incidents grouped into ~110 m areas, for the high-risk-area map."""
  permission_classes = GUARDS

  def get(self, request):
    qs, _team = incidents_in_scope(request.user)
    qs, _applied = filter_incidents(qs, request.query_params, request.user.role == 'general_admin')
    rows = qs.filter(latitude__isnull=False, longitude__isnull=False).values_list(
      'latitude', 'longitude', 'category__category_name', 'ai_severity'
    )[:MAX_POINTS]
    return Response(_cluster(rows))
