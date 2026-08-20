"""
Turbo demo service.

A thin, presentation-friendly wrapper around the dataset replay service
(ml_models/data_replay.py). It replays the REAL training dataset
(vital_signs_dataset.csv) through the live ingest pipeline at a fast,
configurable cadence -- the default is 100 readings at 1 second each
(~100 seconds / 1.7 minutes) instead of the dataset's native 2-minute
cadence (which would take ~3.3 hours for 100 readings).

Every reading goes through the exact same path a real smartwatch hit would:
RF + LSTM inference, the three-tier alert engine, WebSocket pushes to the
patient + guardian dashboards, email and (best-effort) FCM -- nothing is
short-cut.

To make a short demo actually exercise the alert tiers, the service picks a
dataset patient whose first `readings` rows contain high-risk segments (so
Tier 2/3 fire naturally) unless the caller supplies explicit patient ids.

Driven by the turbo demo endpoints in the `demo` and `ml_api` apps.
"""
import logging

from .data_replay import data_replay_service

logger = logging.getLogger(__name__)


class TurboDemoService:
    """Fast dataset-replay wrapper for presentations."""

    def start(self, requester, readings=100, interval_seconds=1.0,
              target_patient_id=None, patient_ids=None):
        """Replay `readings` rows from the training dataset, one every
        `interval_seconds` seconds, through the live ingest pipeline.

        Defaults to 100 readings at 1s => ~100 seconds total. When no
        patient_ids are given, the service auto-selects the dataset patient
        whose first `readings` rows contain the most high-risk segments so
        the alert tiers fire naturally during the demo.
        """
        readings = int(readings)
        interval_seconds = float(interval_seconds)
        if readings <= 0:
            raise ValueError('readings must be a positive integer.')
        if interval_seconds <= 0:
            raise ValueError('interval_seconds must be positive.')

        if not patient_ids:
            patient_ids = data_replay_service.select_demo_patients(
                readings, limit=2,
            )
            logger.info('Turbo demo selected dataset patient(s) %s', patient_ids)

        status = data_replay_service.start(
            requester,
            target_patient_id=target_patient_id,
            interval_seconds=interval_seconds,
            patient_ids=patient_ids,
            max_cycles=1,
            max_readings=readings,
        )
        return self._turbo_shape(status, readings)

    def stop(self):
        data_replay_service.stop()
        return {'status': 'stopped'}

    def status(self):
        return self._turbo_shape(data_replay_service.get_status())

    @staticmethod
    def _turbo_shape(status, fallback_total=None):
        """Return a turbo-oriented view of the shared replay status."""
        total = status.get('max_readings') or fallback_total or status.get('total_readings')
        return {
            'running': status.get('running', False),
            'status': status.get('status', 'idle'),
            'reading_number': status.get('cycle_reading_index', 0),
            'total': total,
            'interval_seconds': status.get('interval_seconds', 1.0),
            'current_patient': status.get('current_patient'),
            'target_patient': status.get('target_patient'),
            'max_readings': status.get('max_readings'),
            'scenario_id': status.get('scenario_id'),
        }


# Process-wide singleton used by the turbo demo endpoints.
turbo_demo_service = TurboDemoService()