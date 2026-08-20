from rest_framework import serializers
from .models import Alert

class AlertSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    resolved = serializers.SerializerMethodField()
    tier = serializers.IntegerField(read_only=True)

    class Meta:
        model = Alert
        fields = [
            'id', 'user', 'alert_type', 'severity', 'title', 'message', 'status',
            'location', 'latitude', 'longitude', 'resolved', 'tier',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'latitude', 'longitude', 'resolved', 'tier',
                            'created_at', 'updated_at']

    def get_user(self, obj):
        return obj.user.get_full_name()

    def get_latitude(self, obj):
        if not isinstance(obj.location, dict):
            return None
        return obj.location.get('latitude', obj.location.get('lat'))

    def get_longitude(self, obj):
        if not isinstance(obj.location, dict):
            return None
        return obj.location.get('longitude', obj.location.get('lng'))

    def get_resolved(self, obj):
        return obj.status == 'resolved'
