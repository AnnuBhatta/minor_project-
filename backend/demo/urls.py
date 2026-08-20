from django.urls import path
from .views import (
    StartFixedScenarioView,
    StartRandomScenarioView,
    StartContinuousScenarioView,
    StartReplayView,
    ReplayPatientsView,
    StopScenarioView,
    ScenarioStatusView,
    TurboStartView,
    TurboStopView,
    TurboStatusView,
    AlertTier1View,
    AlertTier2View,
    AlertTier3View,
    AlertFullDemoView,
)

app_name = 'demo'

urlpatterns = [
    path('fixed-scenario/', StartFixedScenarioView.as_view(), name='fixed-scenario'),
    path('random-scenario/', StartRandomScenarioView.as_view(), name='random-scenario'),
    path('start-continuous/', StartContinuousScenarioView.as_view(), name='start-continuous'),
    path('start/', StartReplayView.as_view(), name='start'),
    path('patients/', ReplayPatientsView.as_view(), name='patients'),
    path('stop/', StopScenarioView.as_view(), name='stop'),
    path('status/', ScenarioStatusView.as_view(), name='status'),
    path('turbo-start/', TurboStartView.as_view(), name='turbo-start'),
    path('turbo-stop/', TurboStopView.as_view(), name='turbo-stop'),
    path('turbo-status/', TurboStatusView.as_view(), name='turbo-status'),
    path('alert/tier1/', AlertTier1View.as_view(), name='alert-tier1'),
    path('alert/tier2/', AlertTier2View.as_view(), name='alert-tier2'),
    path('alert/tier3/', AlertTier3View.as_view(), name='alert-tier3'),
    path('alert/full/', AlertFullDemoView.as_view(), name='alert-full'),
]
