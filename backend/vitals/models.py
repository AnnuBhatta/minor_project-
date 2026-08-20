from django.db import models
from django.conf import settings

class VitalSign(models.Model):
    VITAL_TYPES = [
        ('heart_rate', 'Heart Rate'),
        ('blood_pressure', 'Blood Pressure'),
        ('temperature', 'Temperature'),
        ('oxygen_saturation', 'Oxygen Saturation'),
        ('blood_glucose', 'Blood Glucose'),
        ('weight', 'Weight'),
        ('ecg', 'ECG Data'),
    ]
    
    SOURCE_CHOICES = [
        ('simulated', 'Simulated'),
        ('device', 'Device'),
        ('manual', 'Manual Entry'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vitals')
    vital_type = models.CharField(max_length=50, choices=VITAL_TYPES)
    value = models.JSONField()
    unit = models.CharField(max_length=20, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_abnormal = models.BooleanField(default=False)
    device_id = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='device')
    scenario_id = models.CharField(max_length=100, blank=True, null=True,
                                    help_text='Set when a reading was produced by the demo scenario runner')

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'vital_type', '-timestamp']),
            models.Index(fields=['user', 'source']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.vital_type} - {self.timestamp}"

class Threshold(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='thresholds')
    vital_type = models.CharField(max_length=50, choices=VitalSign.VITAL_TYPES)
    min_value = models.FloatField(blank=True, null=True)
    max_value = models.FloatField(blank=True, null=True)
    custom_name = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        unique_together = ['user', 'vital_type']
    
    def __str__(self):
        return f"{self.user.email} - {self.vital_type} Threshold"