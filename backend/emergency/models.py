from django.db import models
from django.conf import settings
from alerts.models import Alert

class EmergencyEvent(models.Model):
    EVENT_STATUS = [
        ('active', 'Active'),
        ('resolved', 'Resolved'),
        ('cancelled', 'Cancelled'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='emergency_events')
    alert = models.ForeignKey(Alert, on_delete=models.SET_NULL, null=True, blank=True)  # ✅ Now works
    location = models.JSONField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='high')
    status = models.CharField(max_length=20, choices=EVENT_STATUS, default='active')
    is_manual = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_emergencies')
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Emergency {self.id} - {self.user.email} - {self.status}"

class EmergencyNotification(models.Model):
    NOTIFICATION_STATUS = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('read', 'Read'),
    ]
    
    emergency_event = models.ForeignKey(EmergencyEvent, on_delete=models.CASCADE, related_name='notifications')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='emergency_notifications')
    fcm_message_id = models.CharField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=NOTIFICATION_STATUS, default='sent')
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"Notification {self.id} - {self.recipient.email} - {self.status}"