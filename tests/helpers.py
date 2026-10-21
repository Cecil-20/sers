from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User

PASSWORD = 'Str0ng-Pass-9271'
NEW_PASSWORD = 'An0ther-Pass-5518'


def make_user(email, role='general_user', full_name=None, **extra):
  return User.objects.create_user(
    email=email,
    password=PASSWORD,
    full_name=full_name or email.split('@')[0].title(),
    role=role,
    **extra,
  )


def token_for(user):
  return str(RefreshToken.for_user(user).access_token)


def client_for(user):
  client = APIClient()
  client.credentials(HTTP_AUTHORIZATION=f'Bearer {token_for(user)}')
  return client


def rows(response):
  data = response.data
  return data['results'] if isinstance(data, dict) and 'results' in data else data
