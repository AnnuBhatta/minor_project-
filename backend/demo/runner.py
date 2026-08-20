"""
Runs a scenario in a background thread, posting each tick to the real
/api/readings/ingest/ endpoint through Django's request machinery (DRF's
APIClient) -- not a hand-rolled shortcut that calls the inference pipeline
directly. This matters for the "prove it's not hardcoded" requirement: the
demo goes through the exact same serializer validation, permission checks,
and inference pipeline a real device's HTTP request would.

One thread runs per patient at a time; starting a new scenario for a
patient who already has one running stops the old one first.
"""
import logging
import threading
import time
import uuid

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from .scenarios import FIXED_SCENARIO, continuous_ticks, generate_random_scenario

logger = logging.getLogger(__name__)
User = get_user_model()

# In-memory registry of running scenario threads, keyed by patient id.
# A prototype-appropriate choice: acceptable to lose on process restart,
# same tradeoff the project brief's "simple threaded loop" already accepts.
_RUNNING = {}
_LOCK = threading.Lock()


class ScenarioRunner(threading.Thread):
    daemon = True

    def __init__(self, patient, ticks, scenario_id, seconds_per_tick=1.0):
        super().__init__(daemon=True)
        self.patient = patient
        self.ticks = ticks
        self.scenario_id = scenario_id
        self.seconds_per_tick = seconds_per_tick
        self._stop_event = threading.Event()
        self.status = 'pending'
        self.current_tick = 0

    def stop(self):
        self._stop_event.set()

    def run(self):
        self.status = 'running'
        client = APIClient()
        client.force_authenticate(user=self.patient)

        for index, readings in enumerate(self.ticks):
            if self._stop_event.is_set():
                self.status = 'stopped'
                return
            self.current_tick = index + 1
            try:
                client.post('/api/readings/ingest/', {
                    'source': 'simulated',
                    'scenario_id': self.scenario_id,
                    'readings': readings,
                }, format='json')
            except Exception:
                logger.exception('Demo scenario tick failed for patient %s', self.patient.id)
            time.sleep(self.seconds_per_tick)

        self.status = 'completed'
        with _LOCK:
            _RUNNING.pop(self.patient.id, None)


def start_fixed_scenario(patient, seconds_per_tick=1.0):
    return _start(patient, FIXED_SCENARIO, seconds_per_tick, label='fixed')


def start_random_scenario(patient, seconds_per_tick=1.0):
    scenario = generate_random_scenario()
    runner = _start(patient, scenario['ticks'], seconds_per_tick, label=f"random-{scenario['story']}")
    return runner, scenario


class ContinuousRunner(threading.Thread):
    """Runs the continuous simulated stream until stopped. This is the
    'data runs in the backend whenever the web is opened' mode: it never
    completes on its own, so the dashboard always has fresh readings."""

    def __init__(self, patient, scenario_id, seconds_per_tick=1.0):
        super().__init__(daemon=True)
        self.patient = patient
        self.scenario_id = scenario_id
        self.seconds_per_tick = seconds_per_tick
        self._stop_event = threading.Event()
        self.status = 'pending'
        self.current_tick = 0

    def stop(self):
        self._stop_event.set()

    def run(self):
        self.status = 'running'
        client = APIClient()
        client.force_authenticate(user=self.patient)

        for readings in continuous_ticks():
            if self._stop_event.is_set():
                self.status = 'stopped'
                return
            self.current_tick += 1
            try:
                client.post('/api/readings/ingest/', {
                    'source': 'simulated',
                    'scenario_id': self.scenario_id,
                    'readings': readings,
                }, format='json')
            except Exception:
                logger.exception('Continuous demo tick failed for patient %s', self.patient.id)
            time.sleep(self.seconds_per_tick)

        self.status = 'completed'
        with _LOCK:
            _RUNNING.pop(self.patient.id, None)


def start_continuous(patient, seconds_per_tick=1.0):
    """Idempotent start: if the patient already has a running stream,
    return it instead of spawning a duplicate."""
    with _LOCK:
        existing = _RUNNING.get(patient.id)
        if existing and existing.status in ('running', 'pending'):
            return existing
        scenario_id = f"continuous-{uuid.uuid4().hex[:8]}"
        runner = ContinuousRunner(patient, scenario_id, seconds_per_tick=seconds_per_tick)
        _RUNNING[patient.id] = runner
        runner.start()
        return runner


def _start(patient, ticks, seconds_per_tick, label):
    with _LOCK:
        existing = _RUNNING.get(patient.id)
        if existing:
            existing.stop()
        scenario_id = f"{label}-{uuid.uuid4().hex[:8]}"
        runner = ScenarioRunner(patient, ticks, scenario_id, seconds_per_tick=seconds_per_tick)
        _RUNNING[patient.id] = runner
        runner.start()
        return runner


def stop_scenario(patient):
    with _LOCK:
        runner = _RUNNING.get(patient.id)
        if runner:
            runner.stop()
            _RUNNING.pop(patient.id, None)
            return True
        return False


def get_status(patient):
    with _LOCK:
        runner = _RUNNING.get(patient.id)
        if not runner:
            return {'running': False}
        is_continuous = not hasattr(runner, 'ticks')
        return {
            'running': runner.status == 'running',
            'status': runner.status,
            'scenario_id': runner.scenario_id,
            'current_tick': runner.current_tick,
            'total_ticks': len(runner.ticks) if not is_continuous else None,
            'continuous': is_continuous,
        }
