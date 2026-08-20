from django.db import models
from django.conf import settings

class Prediction(models.Model):
    PREDICTION_TYPES = [
        ('health_risk', 'Health Risk'),
        ('heart_disease', 'Heart Disease'),
        ('abnormal_vital', 'Abnormal Vital Sign'),
        ('fall_risk', 'Fall Risk'),
        ('trend_early_warning', 'Trend Early Warning (LSTM)'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='predictions')
    prediction_type = models.CharField(max_length=50, choices=PREDICTION_TYPES)
    input_data = models.JSONField()
    result = models.JSONField()
    risk_score = models.FloatField(null=True, blank=True)
    risk_level = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'prediction_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.prediction_type} - {self.created_at}"