from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from . import runner
from ml_api.views import (
    StartDemoView,
    DemoPatientsView,
    TurboStartDemoView,
    TurboStopDemoView,
    TurboDemoStatusView,
    TriggerTier1AlertView,
    TriggerTier2AlertView,
    TriggerTier3AlertView,
    TriggerFullDemoView,
)


class StartReplayView(StartDemoView):
    """POST /api/demo/start/ -- start replaying the real training dataset
    through the live ingest pipeline (alias of the ml_api StartDemoView)."""
    pass


class ReplayPatientsView(DemoPatientsView):
    """GET /api/demo/patients/ -- list dataset patients (alias of the ml_api
    DemoPatientsView)."""
    pass


class TurboStartView(TurboStartDemoView):
    """POST /api/demo/turbo-start/ -- fast dataset replay for presentations
    (default 100 readings at 1s). Alias of ml_api TurboStartDemoView."""
    pass


class TurboStopView(TurboStopDemoView):
    """POST /api/demo/turbo-stop/ -- stop the turbo demo stream."""
    pass


class TurboStatusView(TurboDemoStatusView):
    """GET /api/demo/turbo-status/ -- current turbo demo progress."""
    pass


class AlertTier1View(TriggerTier1AlertView):
    """POST /api/demo/alert/tier1/ -- guaranteed Tier 1 (Emergency) alert."""
    pass


class AlertTier2View(TriggerTier2AlertView):
    """POST /api/demo/alert/tier2/ -- guaranteed Tier 2 (Health Alert) alert."""
    pass


class AlertTier3View(TriggerTier3AlertView):
    """POST /api/demo/alert/tier3/ -- guaranteed Tier 3 (Trend Alert) alert."""
    pass


class AlertFullDemoView(TriggerFullDemoView):
    """POST /api/demo/alert/full/ -- runs all three guaranteed scenarios."""
    pass


class StartFixedScenarioView(APIView):
    """POST /api/demo/fixed-scenario/ -- the 'fixed scenario' demo button."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        seconds_per_tick = float(request.data.get('seconds_per_tick', 1.0))
        run = runner.start_fixed_scenario(request.user, seconds_per_tick=seconds_per_tick)
        return Response({
            'message': 'Fixed scenario started.',
            'scenario_id': run.scenario_id,
            'total_ticks': len(run.ticks),
            'seconds_per_tick': seconds_per_tick,
        })


class StartRandomScenarioView(APIView):
    """POST /api/demo/random-scenario/ -- the 'random scenario' demo button."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        seconds_per_tick = float(request.data.get('seconds_per_tick', 1.0))
        run, scenario = runner.start_random_scenario(request.user, seconds_per_tick=seconds_per_tick)
        return Response({
            'message': 'Random scenario started.',
            'scenario_id': run.scenario_id,
            'story': scenario['story'],
            'total_ticks': scenario['n_ticks'],
            'onset_tick': scenario['onset_tick'],
            'seconds_per_tick': seconds_per_tick,
        })


class StartContinuousScenarioView(APIView):
    """POST /api/demo/start-continuous/ -- auto-started by the frontend when
    the dashboard opens, so simulated data is always flowing. Idempotent: a
    second call while one is already running returns the existing stream."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        seconds_per_tick = float(request.data.get('seconds_per_tick', 1.0))
        run = runner.start_continuous(request.user, seconds_per_tick=seconds_per_tick)
        return Response({
            'message': 'Continuous simulated data stream running.',
            'scenario_id': run.scenario_id,
            'running': True,
            'continuous': True,
        })


class StopScenarioView(APIView):
    """Stops whatever is running for this user: a scenario stream and/or the
    dataset replay."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        stopped = runner.stop_scenario(request.user)
        from ml_models.data_replay import data_replay_service
        replay_was_running = data_replay_service.is_running()
        data_replay_service.stop()
        return Response({'stopped': stopped, 'replay_stopped': replay_was_running})


class ScenarioStatusView(APIView):
    """Combined status: scenario runner + dataset replay stream."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        scenario = runner.get_status(request.user)
        from ml_models.data_replay import data_replay_service
        return Response({
            **scenario,
            'replay': data_replay_service.get_status(),
        })
