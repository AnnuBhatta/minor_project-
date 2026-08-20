from django.db import models
from django.conf import settings

class UserLocation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='locations')
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy = models.FloatField(blank=True, null=True, help_text='Accuracy in meters')
    altitude = models.FloatField(blank=True, null=True)
    # Retained for compatibility with existing location records.
    location_name = models.CharField(max_length=255, blank=True, null=True)
    speed = models.FloatField(blank=True, null=True)
    heading = models.FloatField(blank=True, null=True)
    is_emergency = models.BooleanField(default=False)
    emergency_event_id = models.IntegerField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    # Retained for compatibility with existing location records.
    device_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp'], name='location_us_user_id_3cbdd7_idx'),
            models.Index(fields=['user', 'timestamp'], name='location_user_timestamp_idx'),
            models.Index(fields=['user', 'is_emergency'], name='location_user_emergency_idx'),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.latitude}, {self.longitude}"


class SafeZone(models.Model):
    """Legacy safe-zone data retained so existing databases are not modified destructively."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='safe_zones')
    name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius = models.FloatField(help_text='Radius in meters')
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'name']
