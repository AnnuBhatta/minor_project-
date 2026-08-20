from rest_framework import serializers
from .models import VitalSign, Threshold

class VitalSignSerializer(serializers.ModelSerializer):
    class Meta:
        model = VitalSign
        fields = '__all__'

class ThresholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Threshold
        fields = '__all__'


class VitalSignInputSerializer(serializers.ModelSerializer):
    """Validate readings submitted by the authenticated user."""

    class Meta:
        model = VitalSign
        fields = ['id', 'vital_type', 'value', 'unit', 'timestamp', 'is_abnormal',
                  'device_id', 'notes', 'source', 'scenario_id']
        read_only_fields = ['id', 'timestamp']
