from django.urls import path
from .views import *

urlpatterns = [
    # Prediction endpoints
    path('predict/health-risk/', HealthRiskPredictionView.as_view(), name='predict-health-risk'),
    path('history/', PredictionHistoryView.as_view(), name='prediction-history'),
    path('status/', ModelStatusView.as_view(), name='model-status'),
    
    # Alert engine endpoints
    path('alert/status/', GetAlertStatusView.as_view(), name='alert-status'),
    path('alert/reset/', ResetAlertEngineView.as_view(), name='alert-reset'),
    
    # Demo simulation endpoints (dataset replay)
    path('demo/start/', StartDemoView.as_view(), name='start-demo'),
    path('demo/stop/', StopDemoView.as_view(), name='stop-demo'),
    path('demo/status/', DemoStatusView.as_view(), name='demo-status'),
    path('demo/patients/', DemoPatientsView.as_view(), name='demo-patients'),

    # Turbo demo endpoints (fast dataset replay for presentations)
    path('demo/turbo-start/', TurboStartDemoView.as_view(), name='turbo-start-demo'),
    path('demo/turbo-stop/', TurboStopDemoView.as_view(), name='turbo-stop-demo'),
    path('demo/turbo-status/', TurboDemoStatusView.as_view(), name='turbo-demo-status'),

    # Guaranteed-alert demo endpoints
    path('demo/alert/tier1/', TriggerTier1AlertView.as_view(), name='demo-alert-tier1'),
    path('demo/alert/tier2/', TriggerTier2AlertView.as_view(), name='demo-alert-tier2'),
    path('demo/alert/tier3/', TriggerTier3AlertView.as_view(), name='demo-alert-tier3'),
    path('demo/alert/full/', TriggerFullDemoView.as_view(), name='demo-alert-full'),
    path('demo/generate-data/', GenerateTrainingDataView.as_view(), name='generate-data'),
    path('demo/train-models/', TrainModelsView.as_view(), name='train-models'),
    path('demo/history/', GetDemoHistoryView.as_view(), name='demo-history'),

    # Manual single-reading processing through the three-tier alert system
    path('process-reading/', ProcessSingleReadingView.as_view(), name='process-reading'),
]