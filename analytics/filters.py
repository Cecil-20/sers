import uuid
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

SEVERITIES = ('low', 'medium', 'high', 'critical', 'unclassified')


def _date(params, key):
  raw = params.get(key)
  if not raw:
    return None
  value = parse_date(str(raw))
  if value is None:
    raise ValidationError({key: 'Use the format YYYY-MM-DD.'})
  return value


def _id(params, key):
  raw = params.get(key)
  if not raw:
    return None
  raw = str(raw)
  try:
    return str(uuid.UUID(raw))
  except ValueError:
    pass
  if raw.isdigit():
    return raw
  raise ValidationError({key: 'Invalid id.'})


def filter_incidents(qs, params, is_admin):
  """Apply date / category / team / severity filters to an already scoped
  queryset. Returns (queryset, applied) where applied lists what was used."""
  applied = {}
  date_from = _date(params, 'date_from')
  date_to = _date(params, 'date_to')
  if date_from and date_to and date_from > date_to:
    raise ValidationError({'date_from': 'Start date must not be after the end date.'})
  if date_from:
    qs = qs.filter(created_at__date__gte=date_from)
    applied['date_from'] = date_from.isoformat()
  if date_to:
    qs = qs.filter(created_at__date__lte=date_to)
    applied['date_to'] = date_to.isoformat()

  category = _id(params, 'category')
  if category:
    qs = qs.filter(category_id=category)
    applied['category'] = category

  team = _id(params, 'team') if is_admin else None
  if team:
    qs = qs.filter(team_id=team)
    applied['team'] = team

  severity = params.get('severity')
  if severity:
    if severity not in SEVERITIES:
      raise ValidationError({'severity': 'Use low, medium, high, critical or unclassified.'})
    if severity == 'unclassified':
      qs = qs.filter(ai_severity__isnull=True)
    else:
      qs = qs.filter(ai_severity=severity)
    applied['severity'] = severity
  return qs, applied
