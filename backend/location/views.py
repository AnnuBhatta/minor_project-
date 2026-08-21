from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import UserLocation
from .serializers import UserLocationSerializer, LiveLocationSerializer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class UpdateLocationView(APIView):
    """
    Update user's current location
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = LiveLocationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Save location
            location = UserLocation.objects.create(
                user=request.user,
                latitude=serializer.validated_data['latitude'],
                longitude=serializer.validated_data['longitude'],
                accuracy=serializer.validated_data.get('accuracy'),
                altitude=serializer.validated_data.get('altitude'),
                speed=serializer.validated_data.get('speed'),
                heading=serializer.validated_data.get('heading'),
                is_emergency=serializer.validated_data.get('is_emergency', False),
                emergency_event_id=serializer.validated_data.get('emergency_event_id')
            )
            
            # Send real-time update via WebSocket
            channel_layer = get_channel_layer()
            
            # Broadcast to user's own channel
            async_to_sync(channel_layer.group_send)(
                f"user_{request.user.id}_location",
                {
                    'type': 'location_update',
                    'location': {
                        'user_id': request.user.id,
                        'user_name': request.user.get_full_name(),
                        'latitude': float(location.latitude),
                        'longitude': float(location.longitude),
                        'accuracy': location.accuracy,
                        'is_emergency': location.is_emergency,
                        'timestamp': location.timestamp.isoformat()
                    }
                }
            )
            
            # If emergency, broadcast to guardian groups
            if location.is_emergency:
                guardians = request.user.guardians.all()
                for guardian in guardians:
                    async_to_sync(channel_layer.group_send)(
                        f"emergency_{guardian.id}",  # ✅ FIXED: Correct group name
                        {
                            'type': 'emergency_location',
                            'location': {
                                'user_id': request.user.id,
                                'user_name': request.user.get_full_name(),
                                'patient_phone': request.user.phone or '',
                                'latitude': float(location.latitude),
                                'longitude': float(location.longitude),
                                'accuracy': location.accuracy,
                                'emergency_event_id': location.emergency_event_id,
                                'timestamp': location.timestamp.isoformat()
                            }
                        }
                    )
            
            return Response({
                'status': 'success',
                'location_id': location.id,
                'timestamp': location.timestamp.isoformat()
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Location update error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LocationHistoryView(generics.ListAPIView):
    """
    Get location history for a user
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserLocationSerializer
    
    def get_queryset(self):
        user_id = self.request.query_params.get('user_id', self.request.user.id)
        limit = int(self.request.query_params.get('limit', 100))
        is_emergency = self.request.query_params.get('is_emergency')

        if int(user_id) != self.request.user.id:
            target_user = User.objects.filter(id=user_id).first()
            if not target_user or self.request.user not in target_user.guardians.all():
                return UserLocation.objects.none()

        queryset = UserLocation.objects.filter(user_id=user_id)
        
        if is_emergency is not None:
            queryset = queryset.filter(is_emergency=is_emergency.lower() == 'true')
        
        return queryset[:limit]

class CurrentLocationView(APIView):
    """
    Get current/latest location of a user
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, user_id=None):
        target_user_id = user_id or request.user.id
        
        if target_user_id != request.user.id:
            target_user = get_object_or_404(User, id=target_user_id)
            if request.user not in target_user.guardians.all():
                return Response({
                    'error': 'You do not have permission to view this location'
                }, status=status.HTTP_403_FORBIDDEN)
        
        latest_location = UserLocation.objects.filter(
            user_id=target_user_id
        ).first()
        
        if not latest_location:
            return Response({
                'message': 'No location data available'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = UserLocationSerializer(latest_location)
        return Response(serializer.data)