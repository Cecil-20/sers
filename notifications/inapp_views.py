from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import InAppNotification


class InAppNotificationSerializer(serializers.ModelSerializer):
    incident_id = serializers.UUIDField(read_only=True)
    reference_no = serializers.CharField(source='incident.reference_no', read_only=True)

    class Meta:
        model = InAppNotification
        fields = ['id', 'kind', 'message', 'is_read', 'created_at', 'incident_id', 'reference_no']
        read_only_fields = fields


def _unread(user):
    return InAppNotification.objects.filter(user=user, is_read=False).count()


class NotificationListView(generics.ListAPIView):
    """The signed-in user's 100 most recent notifications."""
    serializer_class = InAppNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return InAppNotification.objects.none()
        return InAppNotification.objects.filter(user=self.request.user).select_related('incident')[:100]


class UnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({'unread_count': _unread(request.user)})


class MarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        updated = InAppNotification.objects.filter(user=request.user, pk=pk).update(is_read=True)
        if not updated:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'unread_count': _unread(request.user)})


class MarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        InAppNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'unread_count': 0})
