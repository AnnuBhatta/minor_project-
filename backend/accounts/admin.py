from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'phone', 'is_guardian', 'is_active')
    list_filter = ('is_guardian', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Personal Info', {
            'fields': ('phone', 'date_of_birth', 'address', 'profile_picture')
        }),
        ('Emergency Contact', {
            'fields': ('emergency_contact_name', 'emergency_contact_phone', 
                      'emergency_contact_email', 'emergency_contact_relation')
        }),
        ('Medical Info', {
            'fields': ('medical_conditions', 'allergies', 'medications', 'blood_group')
        }),
        ('Roles', {
            'fields': ('is_guardian', 'is_patient')
        }),
        ('Notifications', {
            'fields': ('fcm_token',)
        }),
        ('Guardians', {
            'fields': ('guardians',)
        }),
        ('Activity', {
            'fields': ('last_active', 'is_online')
        }),
    )

admin.site.register(User, CustomUserAdmin)