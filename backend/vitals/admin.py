# admin.py
from django.contrib import admin
from .models import VitalSign, Threshold

@admin.register(VitalSign)
class VitalSignAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_email', 'vital_type', 'get_value_display', 'unit', 'is_abnormal', 'source', 'timestamp')
    list_filter = ('vital_type', 'is_abnormal', 'source', 'timestamp')
    search_fields = ('user__email', 'user__username', 'device_id', 'scenario_id')
    readonly_fields = ('timestamp',)
    list_editable = ('is_abnormal',)

    # Add this line to turn the User dropdown into a simple ID input field 👇
    raw_id_fields = ('user',)

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'

    def get_value_display(self, obj):
        return str(obj.value)
    get_value_display.short_description = 'Value Data'



@admin.register(Threshold)
class ThresholdAdmin(admin.ModelAdmin):
    # Columns shown for Threshold rules
    list_display = ('id', 'user_email', 'vital_type', 'min_value', 'max_value', 'custom_name')
    
    # Sidebar filters
    list_filter = ('vital_type',)
    
    # Text search
    search_fields = ('user__email', 'user__username', 'custom_name')

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'
