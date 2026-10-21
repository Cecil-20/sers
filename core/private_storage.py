import os
import time

import cloudinary.uploader
from cloudinary.utils import private_download_url
from cloudinary_storage.storage import MediaCloudinaryStorage

SIGNED_URL_SECONDS = 300


class PrivateMediaCloudinaryStorage(MediaCloudinaryStorage):
  # Same as the stock storage, but files are uploaded with type
  # "authenticated": their plain URLs stop working and every view of a
  # photo needs a signed, expiring link issued by our own endpoint.

  def _upload(self, name, content):
    options = {
      'use_filename': True,
      'resource_type': self._get_resource_type(name),
      'tags': self.TAG,
      'type': 'authenticated',
    }
    folder = os.path.dirname(name)
    if folder:
      options['folder'] = folder
    return cloudinary.uploader.upload(content, **options)

  def delete(self, name):
    response = cloudinary.uploader.destroy(
      name, invalidate=True, type='authenticated',
      resource_type=self._get_resource_type(name),
    )
    return response['result'] == 'ok'

  def url(self, name):
    # Never hand out a permanent link by accident.
    return ''

  def exists(self, name):
    return False

  def signed_url(self, name, seconds=SIGNED_URL_SECONDS):
    return private_download_url(
      name, 'jpg',
      resource_type=self._get_resource_type(name),
      type='authenticated',
      expires_at=int(time.time()) + seconds,
    )
