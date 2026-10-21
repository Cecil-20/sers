from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .sockets import disconnect_user


class PasswordChangeThrottle(UserRateThrottle):
  scope = 'password_change'
  rate = '10/hour'


class ChangePasswordView(APIView):
  permission_classes = [permissions.IsAuthenticated]
  throttle_classes = [PasswordChangeThrottle]

  def post(self, request):
    user = request.user
    current = str(request.data.get('current_password', ''))
    new = str(request.data.get('new_password', ''))

    if not user.check_password(current):
      raise serializers.ValidationError({'current_password': 'Your current password is incorrect.'})
    if new == current:
      raise serializers.ValidationError(
        {'new_password': 'Choose a password different from your current one.'}
      )
    try:
      validate_password(new, user=user)
    except DjangoValidationError as exc:
      raise serializers.ValidationError({'new_password': list(exc.messages)})

    user.set_password(new)
    user.must_change_password = False
    user.save(update_fields=['password', 'must_change_password'])
    disconnect_user(user)

    # Every token issued before this moment is now revoked, including the
    # caller's own. Hand back fresh ones so this session carries on.
    refresh = RefreshToken.for_user(user)
    return Response({
      'detail': 'Password changed.',
      'access': str(refresh.access_token),
      'refresh': str(refresh),
    })
