from rest_framework import serializers
from .models import UserLocation

class UserLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserLocation
        fields = ['id', 'user', 'latitude', 'longitude', 'accuracy', 
                 'altitude', 'speed', 'heading', 'is_emergency', 
                 'emergency_event_id', 'timestamp']
        read_only_fields = ['id', 'user', 'timestamp']

class LiveLocationSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    accuracy = serializers.FloatField(required=False)
    altitude = serializers.FloatField(required=False)
    speed = serializers.FloatField(required=False)
    heading = serializers.FloatField(required=False)
    is_emergency = serializers.BooleanField(default=False)
    emergency_event_id = serializers.IntegerField(required=False)