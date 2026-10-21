import cloudinary.uploader
from cloudinary import exceptions as cloudinary_exceptions
from django.core.management.base import BaseCommand

from incidents.models import IncidentImage


class Command(BaseCommand):
  help = 'Move already-uploaded incident photos from public to authenticated delivery.'

  def add_arguments(self, parser):
    parser.add_argument('--dry-run', action='store_true')

  def handle(self, *args, **options):
    moved = skipped = failed = 0
    for image in IncidentImage.objects.all():
      name = image.image.name
      if options['dry_run']:
        self.stdout.write(f'would move {name}')
        continue
      try:
        cloudinary.uploader.rename(
          name, name, type='upload', to_type='authenticated', invalidate=True,
        )
        moved += 1
        self.stdout.write(f'moved {name}')
      except cloudinary_exceptions.NotFound:
        skipped += 1
        self.stdout.write(f'skipped {name} (no public copy; probably already private)')
      except Exception as exc:
        failed += 1
        self.stderr.write(f'FAILED {name}: {type(exc).__name__}: {exc}')
    if not options['dry_run']:
      self.stdout.write(f'done: {moved} moved, {skipped} skipped, {failed} failed')
