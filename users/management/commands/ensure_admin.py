import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from users.models import User


class Command(BaseCommand):
  help = 'Create the first admin from ADMIN_EMAIL, ADMIN_PASSWORD and ADMIN_NAME if none exists.'

  def handle(self, *args, **options):
    if User.objects.filter(role='general_admin').exists():
      self.stdout.write('An admin already exists; nothing to do.')
      return
    email = os.environ.get('ADMIN_EMAIL', '').strip().lower()
    password = os.environ.get('ADMIN_PASSWORD', '')
    name = os.environ.get('ADMIN_NAME', '').strip() or 'Administrator'
    if not email or not password:
      self.stdout.write('ADMIN_EMAIL or ADMIN_PASSWORD is not set; skipping.')
      return
    try:
      validate_password(password)
    except ValidationError as exc:
      raise CommandError('ADMIN_PASSWORD is too weak: ' + ' '.join(exc.messages))
    user = User.objects.create_user(
      email=email, password=password, full_name=name, role='general_admin'
    )
    user.must_change_password = True
    user.save(update_fields=['must_change_password'])
    self.stdout.write('Created admin ' + email + '. Remove ADMIN_PASSWORD from the environment now.')
