from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.legal import TERMS_VERSION
from .serializers import UserSerializer


class CurrentUserView(APIView):
  """Returns the authenticated user's own profile, including role."""
  permission_classes = [IsAuthenticated]

  def get(self, request):
    user = request.user
    data = dict(UserSerializer(user).data)
    data['must_change_password'] = user.must_change_password
    data['needs_terms'] = user.accepted_terms_version != TERMS_VERSION
    return Response(data)
