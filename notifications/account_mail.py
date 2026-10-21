import requests
from decouple import config
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def _send(to, subject, text):
  """Send one plain-text email through Resend. Never raises; returns True if sent.
  In DEBUG, an email that cannot be sent is printed instead, so links stay testable."""
  key = config('RESEND_API_KEY', default='')
  sender = config('DEFAULT_FROM_EMAIL', default='')
  ok = False
  if key and sender:
    try:
      r = requests.post(
        'https://api.resend.com/emails',
        headers={'Authorization': f'Bearer {key}'},
        json={'from': sender, 'to': [to], 'subject': subject, 'text': text},
        timeout=8,
      )
      ok = r.ok
      if not ok:
        print(f'Email to {to} was not delivered: {r.status_code} {r.text[:200]}')
    except requests.RequestException as e:
      print(f'Email to {to} failed: {e}')
  if not ok and settings.DEBUG:
    print(f'\n[DEV EMAIL - not delivered] To: {to}\nSubject: {subject}\n{text}\n')
  return ok


def _link(user):
  base = config('FRONTEND_URL', default='http://localhost:5173').rstrip('/')
  uid = urlsafe_base64_encode(force_bytes(user.pk))
  token = default_token_generator.make_token(user)
  return f'{base}/reset-password?uid={uid}&token={token}'


def send_reset_link(user, invite=False):
  hours = int(settings.PASSWORD_RESET_TIMEOUT // 3600)
  link = _link(user)
  if invite:
    subject = 'Set up your SERIMS account'
    intro = 'An administrator created a SERIMS account for you. Use the link below to choose your password.'
  else:
    subject = 'Reset your SERIMS password'
    intro = 'Use the link below to choose a new SERIMS password.'
  text = (
    f'Hello {user.full_name},\n\n{intro}\n\n{link}\n\n'
    f'The link works once and expires in {hours} hours. '
    'If you were not expecting this email, you can ignore it.'
  )
  return _send(user.email, subject, text)


def send_password_reset_notice(user, admin):
  """Tell a user an administrator set a temporary password. The password is not included."""
  text = (
    f'Hello {user.full_name},\n\n'
    f'An administrator ({admin.full_name}) reset your SERIMS password. '
    'You will be asked to choose a new password the next time you sign in.\n\n'
    'If you were not expecting this, contact your administrator.'
  )
  return _send(user.email, 'Your SERIMS password was reset', text)
