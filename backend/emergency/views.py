from rest_framework import status, generics, permissions, views
from rest_framework.response import Response
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import EmergencyEvent, EmergencyNotification
from .serializers import EmergencyEventSerializer, EmergencyNotificationSerializer
from .services import send_emergency_alert, send_emergency_to_contacts
from alerts.models import Alert

class EmergencyEventListCreateView(generics.ListCreateAPIView):
    """
    List all emergency events or create a new one
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmergencyEventSerializer

    def get_queryset(self):
        return EmergencyEvent.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        location = self.request.data.get('location', {'lat': 0, 'lng': 0})
        severity = self.request.data.get('severity', 'high')
        description = self.request.data.get('description', '')
        
        emergency = serializer.save(
            user=self.request.user,
            location=location,
            severity=severity,
            description=description,
            is_manual=True
        )
        
        # Send emergency alerts
        send_emergency_alert(emergency)

        # Backup email channel to guardians (async, best-effort)
        try:
            from alerts.services import send_alert_email
            send_alert_email(
                patient=self.request.user,
                alert_type='emergency',
                severity=emergency.severity or 'high',
                title='🚨 EMERGENCY ALERT',
                message=emergency.description or f"Emergency event triggered by {self.request.user.get_full_name()}",
                timestamp=emergency.created_at,
                location=emergency.location,
            )
        except Exception:
            import logging
            logging.getLogger('emergency').exception(
                'Failed to send emergency email for user %s', self.request.user.id,
            )

class EmergencyEventDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update or delete a specific emergency event
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmergencyEventSerializer

    def get_queryset(self):
        return EmergencyEvent.objects.filter(user=self.request.user)

class EmergencyResolveView(generics.UpdateAPIView):
    """
    Resolve an emergency event
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmergencyEventSerializer

    def get_queryset(self):
        return EmergencyEvent.objects.filter(user=self.request.user)

    def update(self, request, *args, **kwargs):
        emergency = self.get_object()
        emergency.status = 'resolved'
        emergency.resolved_at = timezone.now()
        emergency.resolved_by = request.user
        emergency.save()
        
        # Also resolve the associated alert if exists
        if emergency.alert:
            emergency.alert.status = 'resolved'
            emergency.alert.save()
        
        serializer = self.get_serializer(emergency)
        return Response(serializer.data)

class EmergencyCancelView(generics.UpdateAPIView):
    """
    Cancel an emergency event
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmergencyEventSerializer

    def get_queryset(self):
        return EmergencyEvent.objects.filter(user=self.request.user)

    def update(self, request, *args, **kwargs):
        emergency = self.get_object()
        emergency.status = 'cancelled'
        emergency.notes = request.data.get('notes', 'Cancelled by user')
        emergency.save()
        
        # Cancel the associated alert if exists
        if emergency.alert:
            emergency.alert.status = 'ignored'
            emergency.alert.save()
        
        serializer = self.get_serializer(emergency)
        return Response(serializer.data)

class EmergencyNotificationListView(generics.ListAPIView):
    """
    List all emergency notifications for the current user
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmergencyNotificationSerializer

    def get_queryset(self):
        return EmergencyNotification.objects.filter(recipient=self.request.user)

class EmergencyNotificationDetailView(generics.RetrieveAPIView):
    """
    Get a specific emergency notification
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmergencyNotificationSerializer

    def get_queryset(self):
        return EmergencyNotification.objects.filter(recipient=self.request.user)

class MarkNotificationReadView(generics.UpdateAPIView):
    """
    Mark a notification as read
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmergencyNotificationSerializer

    def get_queryset(self):
        return EmergencyNotification.objects.filter(recipient=self.request.user)

    def update(self, request, *args, **kwargs):
        notification = self.get_object()
        notification.status = 'read'
        notification.read_at = timezone.now()
        notification.save()
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data)

class ActiveEmergenciesView(generics.ListAPIView):
    """
    List all active emergencies for guardians
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmergencyEventSerializer

    def get_queryset(self):
        user = self.request.user

        # Only patients who approved this user as guardian (consent workflow).
        from accounts.models import GuardianRequest
        patient_ids = GuardianRequest.objects.filter(
            guardian=user, status='approved',
        ).values_list('patient_id', flat=True)

        # Get active emergencies for these patients
        return EmergencyEvent.objects.filter(
            user_id__in=patient_ids,
            status='active'
        ).order_by('-created_at')
