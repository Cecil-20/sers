from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Read-only representation of the authenticated user's own profile."""

    class Meta:
        model = User
        fields = [
            'id',
            'full_name',
            'email',
            'phone_number',
            'role',
            'is_active',
            'is_staff',
            'created_at',
        ]
        read_only_fields = fields
