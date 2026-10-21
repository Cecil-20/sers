from django.core.exceptions import ValidationError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from teams.models import EmergencyCategory
from .services import assist_report

MIN_CHARS = 10
MAX_CHARS = 1500


class AssistThrottle(UserRateThrottle):
  scope = 'ai_assist'
  rate = '30/hour'


def _category_name(raw):
  try:
    category = EmergencyCategory.objects.filter(pk=raw).first()
  except (ValueError, ValidationError):
    return ''
  return category.category_name if category else ''


class ReportAssistView(APIView):
  """Guidance while a reporter fills in the form. On demand, not per keystroke."""
  permission_classes = [permissions.IsAuthenticated]
  throttle_classes = [AssistThrottle]

  def post(self, request):
    description = str(request.data.get('description', '')).strip()
    if len(description) < MIN_CHARS:
      return Response(
        {'description': 'Write a few words about the emergency first.'},
        status=status.HTTP_400_BAD_REQUEST,
      )
    name = _category_name(request.data.get('category')) or 'Unspecified emergency'
    return Response(assist_report(description[:MAX_CHARS], name))
