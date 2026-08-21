from django.urls import path
from .views import (
    VitalHistoryView, VitalLatestView, VitalListCreateView, VitalTrendView,
    WeeklyReportView, DailyChartView, VitalReadingIngestView,
)

app_name = 'vitals'

urlpatterns = [
    path('', VitalListCreateView.as_view(), name='vital-list-create'),
    path('latest/', VitalLatestView.as_view(), name='vital-latest'),
    path('history/', VitalHistoryView.as_view(), name='vital-history'),
    path('trend/', VitalTrendView.as_view(), name='vital-trend'),
    path('weekly-report/', WeeklyReportView.as_view(), name='vital-weekly-report'),
    path('daily-chart/', DailyChartView.as_view(), name='vital-daily-chart'),
    # ✅ Ingest endpoint for data replay
    path('ingest/', VitalReadingIngestView.as_view(), name='vital-ingest'),
]