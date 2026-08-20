from rest_framework import serializers
from .models import EmergencyEvent, EmergencyNotification
from accounts.serializers import UserSerializer

class EmergencyEventSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    resolved_by_details = UserSerializer(source='resolved_by', read_only=True)
    
    class Meta:
        model = EmergencyEvent
        fields = [
            'id', 'user', 'user_details', 'alert', 'location', 'severity',
            'status', 'is_manual', 'description', 'created_at', 'resolved_at',
            'resolved_by', 'resolved_by_details', 'notes'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'resolved_at', 'resolved_by']

class EmergencyNotificationSerializer(serializers.ModelSerializer):
    recipient_details = UserSerializer(source='recipient', read_only=True)
    emergency_details = EmergencyEventSerializer(source='emergency_event', read_only=True)
    
    class Meta:
        model = EmergencyNotification
        fields = [
            'id', 'emergency_event', 'emergency_details', 'recipient', 
            'recipient_details', 'fcm_message_id', 'title', 'body', 'data',
            'status', 'sent_at', 'delivered_at', 'read_at', 'error_message'
        ]
        read_only_fields = ['id', 'sent_at']