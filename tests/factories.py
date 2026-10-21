import uuid

from django.db.models import NOT_PROVIDED

from incidents.models import Incident
from teams.models import EmergencyCategory


def make_category(team, name='Medical Emergency'):
  return EmergencyCategory.objects.create(category_name=name, team=team)


def make_incident(reporter, category, **extra):
  method = Incident._meta.get_field('report_method')
  data = {
    'reporter': reporter,
    'category': category,
    'team': category.team,
    'description': 'Smoke visible from the second floor of the library.',
    'latitude': -0.4167,
    'longitude': 36.95,
    'status': 'submitted',
    'reference_no': f'T-{uuid.uuid4().hex[:8]}',
  }
  if method.default is NOT_PROVIDED and method.choices:
    data['report_method'] = method.choices[0][0]
  data.update(extra)
  return Incident.objects.create(**data)
