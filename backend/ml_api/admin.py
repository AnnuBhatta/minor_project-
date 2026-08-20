from django.contrib import admin
from .models import Prediction

@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ['user', 'prediction_type', 'risk_level', 'risk_score', 'created_at']
    list_filter = ['prediction_type', 'risk_level', 'created_at']
    search_fields = ['user__email', 'user__username']
    readonly_fields = ['created_at']
    ordering = ['-created_at']