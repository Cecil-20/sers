from rest_framework import serializers
from .models import Incident, IncidentImage

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = ('image/jpeg', 'image/png', 'image/webp')


class IncidentImageSerializer(serializers.ModelSerializer):
  class Meta:
    model = IncidentImage
    fields = ['id', 'uploaded_at']


class IncidentSerializer(serializers.ModelSerializer):
  images = IncidentImageSerializer(many=True, read_only=True)
  uploaded_image = serializers.ImageField(
    write_only=True, required=False, allow_null=True
  )

  class Meta:
    model = Incident
    fields = [
      'id', 'reference_no', 'reporter', 'category', 'team', 'report_method',
      'description', 'custom_type_text', 'latitude', 'longitude', 'status',
      'ai_severity', 'ai_classification', 'ai_protocol', 'created_at', 'resolved_at',
      'images', 'uploaded_image',
    ]
    read_only_fields = [
      'reference_no', 'team', 'ai_severity', 'ai_classification', 'ai_protocol',
      'status', 'created_at',
    ]

  def validate_uploaded_image(self, value):
    if value is None:
      return value
    if value.size > MAX_IMAGE_BYTES:
      raise serializers.ValidationError('Image must be 5 MB or smaller.')
    content_type = getattr(value, 'content_type', None)
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
      raise serializers.ValidationError('Use a JPEG, PNG or WebP image.')
    return value

  def create(self, validated_data):
    image_file = validated_data.pop('uploaded_image', None)
    incident = Incident.objects.create(**validated_data)
    if image_file:
      IncidentImage.objects.create(incident=incident, image=image_file)
    return incident
