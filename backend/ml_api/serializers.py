from rest_framework import serializers
from .models import Prediction

class PredictionSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()
    
    class Meta:
        model = Prediction
        fields = ['id', 'user', 'user_email', 'prediction_type', 'input_data', 
                 'result', 'risk_score', 'risk_level', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']
    
    def get_user_email(self, obj):
        return obj.user.email

class HealthRiskPredictionSerializer(serializers.Serializer):
    # Features used by the trained Random Forest model
    heart_rate = serializers.FloatField(min_value=30, max_value=220, required=False)
    oxygen_saturation = serializers.FloatField(min_value=50, max_value=100, required=False)
    systolic_bp = serializers.FloatField(min_value=50, max_value=260, required=False)
    diastolic_bp = serializers.FloatField(min_value=30, max_value=160, required=False)
    derived_hr = serializers.FloatField(min_value=0, max_value=1, required=False)
    derived_pulse_pressure = serializers.FloatField(min_value=0, max_value=200, required=False)

    # Backward-compatible fields (ignored by the current model)
    age = serializers.FloatField(min_value=0, max_value=120, required=False)
    bmi = serializers.FloatField(min_value=10, max_value=60, required=False)
    blood_pressure = serializers.FloatField(min_value=80, max_value=250, required=False)
    cholesterol = serializers.FloatField(min_value=100, max_value=600, required=False)
    blood_sugar = serializers.FloatField(min_value=40, max_value=500, required=False)
    physical_activity = serializers.FloatField(min_value=0, max_value=300, required=False)
    stress_level = serializers.FloatField(min_value=1, max_value=10, required=False)
    sleep_hours = serializers.FloatField(min_value=0, max_value=24, required=False)