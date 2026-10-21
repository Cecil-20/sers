from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, permissions, serializers
from rest_framework.throttling import AnonRateThrottle

from .models import User


class RegisterThrottle(AnonRateThrottle):
    rate = '20/hour'  # slows down scripted account creation


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone_number', 'password']

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate(self, attrs):
        # Run Django's configured password validators, including the
        # "too similar to your name/email" check, which needs a user object.
        candidate = User(email=attrs.get('email'), full_name=attrs.get('full_name'))
        try:
            validate_password(attrs['password'], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': list(exc.messages)})
        return attrs

    def create(self, validated_data):
        # The role is deliberately NOT accepted from the request. Anyone who
        # signs up themselves is a general user (a reporter); team leaders and
        # members are created by an administrator.
        return User.objects.create_user(role='general_user', **validated_data)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    # Public endpoint: ignore any (possibly stale) token the browser sends,
    # otherwise an expired token would turn signup into a 401.
    authentication_classes = []
    throttle_classes = [RegisterThrottle]
