import re
from .models import AuditLog

UUID = r'[0-9a-fA-F-]{36}'
RULES = [
  (re.compile(r'^/api/incidents/(?P<pk>' + UUID + r')/assign/$'),
   'Assigned responders to incident'),
  (re.compile(r'^/api/incidents/(?P<pk>' + UUID + r')/status/$'),
   'Changed incident status'),
  (re.compile(r'^/api/hotline/calls/$'), 'Logged hotline call'),
  (re.compile(r'^/api/analytics/reports/generate/$'), 'Generated analytics report'),
]
UNSAFE = ('POST', 'PATCH', 'DELETE')
VERBS = {'POST': 'Created', 'PATCH': 'Updated', 'DELETE': 'Deleted'}
RESOURCES = {'teams': 'team', 'categories': 'category', 'accounts': 'account'}


def _data(response):
  data = getattr(response, 'data', None)
  return data if isinstance(data, dict) else {}


def _action(label, response):
  status = _data(response).get('status')
  if status and 'status' in label.lower():
    return f'{label} to {status}'
  return label


def _entity(match, response):
  name = _data(response).get('file_name')
  if name:
    return f'Report {name}'
  ref = _data(response).get('reference_no')
  if ref:
    return f'Incident {ref}'
  pk = match.groupdict().get('pk')
  if not pk:
    return 'Incident'
  from incidents.models import Incident
  ref = Incident.objects.filter(pk=pk).values_list('reference_no', flat=True).first()
  return f'Incident {ref or pk}'


def _manage(request, response):
  parts = [p for p in request.path.split('/') if p]
  if len(parts) < 3 or parts[:2] != ['api', 'manage']:
    return None
  resource = RESOURCES.get(parts[2])
  if not resource:
    return None
  data = _data(response)
  name = (data.get('team_name') or data.get('category_name') or data.get('email')
          or (parts[3] if len(parts) > 3 else ''))
  if parts[-1] == 'reset-password':
    label = 'Reset account password'
  elif parts[-1] == 'send-reset-link':
    label = 'Sent password reset link'
  else:
    label = f'{VERBS[request.method]} {resource}'
  return label, f'{resource.title()} {name}'.strip()


def _write(user, action, entity):
  AuditLog.objects.create(user=user, action=action[:150], entity_affected=entity[:100])


def _record(request, response):
  user = getattr(request, 'user', None)
  if not user or not user.is_authenticated:
    return
  managed = _manage(request, response)
  if managed:
    _write(user, *managed)
    return
  if request.method != 'POST':
    return
  for pattern, label in RULES:
    match = pattern.match(request.path)
    if match:
      _write(user, _action(label, response), _entity(match, response))
      return


def _safe_record(request, response):
  try:
    _record(request, response)
  except Exception as e:
    print(f'Audit log error: {e}')


class AuditLogMiddleware:
  def __init__(self, get_response):
    self.get_response = get_response

  def __call__(self, request):
    response = self.get_response(request)
    if request.method in UNSAFE and 200 <= response.status_code < 300:
      _safe_record(request, response)
    return response
