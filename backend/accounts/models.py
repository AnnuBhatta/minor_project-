from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    phone = models.CharField(max_length=15, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # Emergency Contacts
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True, null=True)
    emergency_contact_email = models.EmailField(blank=True, null=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True, null=True)
    
    # Medical Information
    medical_conditions = models.TextField(blank=True, null=True, help_text="List any medical conditions")
    allergies = models.TextField(blank=True, null=True, help_text="List any allergies")
    medications = models.TextField(blank=True, null=True, help_text="Current medications")
    blood_group = models.CharField(max_length=5, blank=True, null=True, choices=[
        ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-')
    ])
    
    # Profile
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    
    # Roles
    is_guardian = models.BooleanField(default=False, help_text="Is this user a guardian/emergency contact?")
    is_patient = models.BooleanField(default=True, help_text="Is this user a patient?")
    
    # FCM Token for push notifications
    fcm_token = models.CharField(max_length=255, blank=True, null=True)
    
    # Guardian relationships
    guardians = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='patients')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Activity tracking
    last_active = models.DateTimeField(blank=True, null=True)
    is_online = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['is_guardian']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def get_emergency_contacts(self):
        """Get all emergency contacts including guardians"""
        contacts = []
        
        # Add direct emergency contacts
        if self.emergency_contact_email:
            contacts.append({
                'name': self.emergency_contact_name or 'Emergency Contact',
                'email': self.emergency_contact_email,
                'phone': self.emergency_contact_phone,
                'relation': self.emergency_contact_relation or 'Emergency Contact'
            })
        
        # Add guardians
        for guardian in self.guardians.all():
            contacts.append({
                'name': guardian.get_full_name(),
                'email': guardian.email,
                'phone': guardian.phone,
                'relation': 'Guardian'
            })
        
        return contacts


class GuardianRequest(models.Model):
    """
    A patient asks a guardian to monitor them. The guardian must approve the
    request before any alerts are sent, giving consent before the link exists.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='guardian_requests')
    guardian = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patient_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True, null=True, help_text="Optional note from the patient to the guardian")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['patient', 'guardian'],
                name='unique_patient_guardian_request',
            ),
        ]

    def __str__(self):
        return f"{self.patient.get_full_name()} → {self.guardian.get_full_name()} ({self.status})"
    