from rest_framework import generics, permissions, viewsets
from .models import Alert
from .serializers import AlertSerializer

class AlertViewSet(viewsets.ModelViewSet):
    """ViewSet for Alert model"""
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer


class AlertListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AlertSerializer
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        if user.is_guardian:
            qs = Alert.objects.filter(user__in=user.patients.all())
            pid = self.request.query_params.get('user_id')
            if pid:
                qs = qs.filter(user_id=pid)
            return qs
        return Alert.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AlertDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AlertSerializer