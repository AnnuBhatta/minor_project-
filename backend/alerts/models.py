from django.db import models
from django.conf import settings

class Alert(models.Model):
    ALERT_TYPES = [
        ('abnormal_vital', 'Abnormal Vital Sign'),
        ('emergency', 'Emergency Alert'),
        ('medication_reminder', 'Medication Reminder'),
        ('appointment_reminder', 'Appointment Reminder'),
        ('system', 'System Alert'),
    ]
    
    ALERT_SEVERITY = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    ALERT_STATUS = [
        ('pending', 'Pending'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('ignored', 'Ignored'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    severity = models.CharField(max_length=20, choices=ALERT_SEVERITY, default='medium')
    title = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=ALERT_STATUS, default='pending')
    location = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.alert_type} - {self.created_at}"

    @property
    def tier(self):
        """Alert tier, derived from the delivery metadata (see
        ml_models/alert_delivery.TIER_META)."""
        if self.alert_type == 'emergency' and self.severity == 'critical':
            return 1
        if self.alert_type == 'abnormal_vital' and self.severity == 'high':
            return 2
        if self.alert_type == 'abnormal_vital' and self.severity == 'medium':
            return 3
        return None