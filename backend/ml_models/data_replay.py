"""
Dataset replay service.

Streams the real training dataset (vital_signs_dataset.csv) through the live
ingest pipeline exactly as a smartwatch would, so the RF + LSTM models and the
three-tier alert system run against real (training) data -- no hardware needed.

How it works
------------
* The CSV is loaded once and cached. Rows are grouped by patient and sorted
  chronologically (Patient ID, then Timestamp).
* A background thread walks the rows in order, cycling through every dataset
  patient and looping back to the first patient when it runs out.
* Each row is POSTed to /api/readings/ingest/ through DRF's APIClient
  authenticated as the requesting user, with an optional per-reading
  `patient_id` so a guardian can replay data into one of their patients.
  That means every tick goes through the *same* serializer validation,
  RF + LSTM inference, three-tier alert engine, WebSocket push, email and
  FCM delivery a real device's HTTP request would -- nothing is short-cut.
* The server assigns live timestamps (auto_now_add), so dashboards always
  show "now". The dataset's own (historical) timestamps only control the
  ordering within a patient's stream.

The service is a process-wide singleton (`data_replay_service`) driven by the
demo control endpoints in the `demo` and `ml_api` apps.
"""
import logging
import random
import threading
import time
import uuid
from pathlib import Path

import pandas as pd
from rest_framework.test import APIClient

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / 'data'
DEFAULT_CSV_PATH = DATA_DIR / 'vital_signs_dataset.csv'


class DataReplayService:
    """Loads the training CSV and replays it as simulated live data."""

    def __init__(self, csv_path=DEFAULT_CSV_PATH):
        self.csv_path = Path(csv_path)
        self._patients = None       # dataset patient id -> chronological row dicts
        self._patient_ids = []      # ordered dataset patient ids
        self._total_readings = 0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._status = {
            'running': False,
            'status': 'idle',
            'scenario_id': None,
            'cycle': 0,
            'current_patient': None,
            'patient_reading_count': 0,
            'patient_index': 0,
            'cycle_reading_index': 0,
            'reading_index': 0,
            'total_readings': 0,
            'interval_seconds': 2.0,
            'target_patient': None,
            'dataset_patients': 0,
            'dataset_readings': 0,
            'max_readings': None,
            'sample_readings': None,
        }

    # ------------------------------------------------------------------ #
    # Dataset loading
    # ------------------------------------------------------------------ #
    def load_dataset(self, force=False):
        """Load + cache the CSV. Raises FileNotFoundError with a friendly
        message if the training dataset is missing."""
        with self._lock:
            if self._patients is not None and not force:
                return
            if not self.csv_path.exists():
                raise FileNotFoundError(
                    f'Training dataset not found at {self.csv_path}. '
                    'Place vital_signs_dataset.csv under ml_models/data/.'
                )

            df = pd.read_csv(self.csv_path)
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            df = df.sort_values(['Patient ID', 'Timestamp'])

            patients = {}
            for pid, group in df.groupby('Patient ID', sort=True):
                patients[int(pid)] = group.to_dict('records')
            self._patients = patients
            self._patient_ids = list(patients.keys())
            self._total_readings = len(df)
            self._status['dataset_patients'] = len(patients)
            self._status['total_readings'] = len(df)
            self._status['dataset_readings'] = len(df)
            logger.info(
                'Dataset replay ready: %s patients, %s readings',
                len(patients), len(df),
            )

    def list_patients(self):
        """Return an ordered summary of every patient in the dataset."""
        self.load_dataset()
        patients = []
        for pid in self._patient_ids:
            rows = self._patients[pid]
            patients.append({
                'patient_id': pid,
                'reading_count': len(rows),
                'start_time': rows[0]['Timestamp'].isoformat(),
                'end_time': rows[-1]['Timestamp'].isoformat(),
            })
        return patients

    def select_demo_patients(self, n_readings, limit=1):
        """Pick the dataset patient(s) with the most 'High Risk' readings
        inside their first `n_readings` rows, so a short turbo demo naturally
        trips the alert tiers (Tier 2 needs 3 consecutive RF-high readings)."""
        self.load_dataset()
        scored = []
        for pid in self._patient_ids:
            rows = self._patients[pid][:n_readings]
            high = sum(
                1 for r in rows
                if str(r.get('Risk Category', '')).strip().lower().startswith('high')
            )
            scored.append((high, pid))
        scored.sort(reverse=True)
        picked = [pid for _, pid in scored[:limit]]
        return picked if picked else self._patient_ids[:limit]

    # ------------------------------------------------------------------ #
    # Streaming
    # ------------------------------------------------------------------ #
    @staticmethod
    def _row_to_readings(row):
        """Turn one dataset row into the ingest batch shape (4 vital reads)."""
        return [
            {'vital_type': 'heart_rate', 'value': {'heart_rate': float(row['Heart Rate'])}},
            {'vital_type': 'oxygen_saturation', 'value': {'spo2': float(row['Oxygen Saturation'])}},
            {
                'vital_type': 'blood_pressure',
                'value': {
                    'systolic': float(row['Systolic Blood Pressure']),
                    'diastolic': float(row['Diastolic Blood Pressure']),
                },
            },
        ]

    def start(self, requester, target_patient_id=None, interval_seconds=2.0,
              patient_ids=None, max_cycles=None, max_readings=None,
              sample_readings=None):
        """Start (or restart) the replay stream for `requester`.

        Readings are written to the account of `target_patient_id`
        (defaults to the requester). The requester may be the patient
        themselves or one of their guardians -- the ingest endpoint performs
        the same permission check a real device would face.

        `max_readings` stops the stream after that many individual readings
        (used by the fast "turbo demo": e.g. 100 readings at 1s = ~100s).

        `sample_readings` replays a random subset of that many rows drawn from
        the real dataset (still chronological), so the demo uses the genuine
        200k training data but finishes quickly instead of replaying every
        one of the 200,258 rows.
        """
        self.load_dataset()
        if requester is None or not getattr(requester, 'id', None):
            raise ValueError('An authenticated user is required to start the replay.')

        target_patient_id = int(target_patient_id or requester.id)
        interval_seconds = float(interval_seconds)
        if interval_seconds <= 0:
            raise ValueError('interval_seconds must be positive.')
        if max_readings is not None:
            max_readings = int(max_readings)
            if max_readings <= 0:
                raise ValueError('max_readings must be positive.')
        if sample_readings is not None:
            sample_readings = int(sample_readings)
            if sample_readings <= 0:
                raise ValueError('sample_readings must be positive.')

        selected_ids = None
        if patient_ids:
            selected_ids = {int(p) for p in patient_ids}
            missing = sorted(selected_ids - set(self._patient_ids))
            if missing:
                raise ValueError(f'Unknown dataset patient(s): {missing}')

        # Pre-compute the sample size so the status shows the real target
        # ("Reading 50 of 100") from the very first poll, not 200,258.
        sample_size = None
        if sample_readings is not None:
            pool_size = sum(
                len(self._patients[pid]) for pid in self._patient_ids
                if selected_ids is None or pid in selected_ids
            )
            sample_size = min(sample_readings, pool_size)

        with self._lock:
            self._stop()
            self._stop_event = threading.Event()
            scenario_id = f'dataset-replay-{uuid.uuid4().hex[:8]}'
            self._status.update({
                'running': True,
                'status': 'running',
                'scenario_id': scenario_id,
                'cycle': 0,
                'current_patient': None,
                'patient_reading_count': 0,
                'patient_index': 0,
                'cycle_reading_index': 0,
                'reading_index': 0,
                'interval_seconds': interval_seconds,
                'target_patient': target_patient_id,
                'max_readings': max_readings,
                'sample_readings': sample_size,
            })
            if sample_size is not None:
                self._status['total_readings'] = sample_size
            self._thread = threading.Thread(
                target=self._run,
                args=(requester.id, target_patient_id, interval_seconds,
                      selected_ids, max_cycles, max_readings, sample_size),
                daemon=True,
            )
            self._thread.start()
        return self.get_status()

    def _run(self, requester_id, target_patient_id, interval_seconds,
             selected_ids, max_cycles, max_readings=None, sample_readings=None):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            requester = User.objects.get(id=requester_id)
        except User.DoesNotExist:
            logger.error('Replay requester %s no longer exists', requester_id)
            self._status.update({'running': False, 'status': 'error'})
            return

        client = APIClient()
        client.force_authenticate(user=requester)
        ids = [p for p in self._patient_ids
               if selected_ids is None or p in selected_ids]

        # ---- Sampled mode: replay a random subset of the real dataset ----
        # Draw `sample_readings` rows at random from the selected patients,
        # keep them in chronological order, and replay just those. Fast for
        # a presentation, but every row is still genuine training data that
        # runs the real RF + LSTM + 3-tier pipeline.
        if sample_readings:
            pool = [(pid, row) for pid in ids for row in self._patients[pid]]
            picked = random.sample(pool, min(sample_readings, len(pool)))
            picked.sort(key=lambda item: item[1]['Timestamp'])
            self._status.update({
                'running': True,
                'status': 'running',
                'total_readings': len(picked),
                'cycle_reading_index': 0,
            })
            global_index = 0
            for pid, row in picked:
                if self._stop_event.is_set():
                    self._status.update({'running': False, 'status': 'stopped'})
                    return
                global_index += 1
                self._status.update({
                    'current_patient': pid,
                    'patient_index': global_index,
                    'cycle_reading_index': global_index,
                    'reading_index': global_index,
                })
                try:
                    response = client.post('/api/readings/ingest/', {
                        'source': 'simulated',
                        'scenario_id': self._status['scenario_id'],
                        'patient_id': target_patient_id,
                        'readings': self._row_to_readings(row),
                    }, format='json')
                    if response.status_code >= 400:
                        logger.warning(
                            'Replay tick %s rejected: %s',
                            global_index, response.data,
                        )
                except Exception:
                    logger.exception(
                        'Replay tick %s failed for target patient %s',
                        global_index, target_patient_id,
                    )
                time.sleep(interval_seconds)
            self._status.update({'running': False, 'status': 'completed'})
            return

        self._status.update({'running': True, 'status': 'running'})
        cycle = 0
        global_index = 0
        try:
            while max_cycles is None or cycle < max_cycles:
                cycle += 1
                self._status['cycle'] = cycle
                cycle_index = 0
                for pid in ids:
                    if self._stop_event.is_set():
                        self._status.update({'running': False, 'status': 'stopped'})
                        return
                    rows = self._patients[pid]
                    self._status['current_patient'] = pid
                    self._status['patient_reading_count'] = len(rows)
                    for row in rows:
                        if self._stop_event.is_set():
                            self._status.update({'running': False, 'status': 'stopped'})
                            return
                        if max_readings is not None and global_index >= max_readings:
                            self._status.update({'running': False, 'status': 'completed'})
                            return
                        cycle_index += 1
                        global_index += 1
                        self._status['patient_index'] = cycle_index
                        self._status['cycle_reading_index'] = cycle_index
                        self._status['reading_index'] = global_index

                        try:
                            response = client.post('/api/readings/ingest/', {
                                'source': 'simulated',
                                'scenario_id': self._status['scenario_id'],
                                'patient_id': target_patient_id,
                                'readings': self._row_to_readings(row),
                            }, format='json')
                            if response.status_code >= 400:
                                logger.warning(
                                    'Replay tick %s rejected: %s',
                                    global_index, response.data,
                                )
                        except Exception:
                            logger.exception(
                                'Replay tick %s failed for target patient %s',
                                global_index, target_patient_id,
                            )
                        time.sleep(interval_seconds)
            self._status.update({'running': False, 'status': 'completed'})
        except Exception:
            logger.exception('Dataset replay thread crashed')
            self._status.update({'running': False, 'status': 'error'})

    def stop(self):
        with self._lock:
            self._stop()

    def _stop(self):
        """Stop any running thread and mark the stream stopped. Caller must
        hold the lock."""
        if self._thread is not None and self._thread.is_alive():
            self._stop_event.set()
        self._thread = None
        if self._status.get('running'):
            self._status.update({'running': False, 'status': 'stopped'})

    def is_running(self):
        return bool(self._status.get('running'))

    def get_status(self):
        with self._lock:
            status = dict(self._status)
            status['dataset_patients'] = len(self._patient_ids) or self._status.get('dataset_patients', 0)
            if status['total_readings'] == 0:
                status['total_readings'] = self._total_readings
            if status['dataset_readings'] == 0:
                status['dataset_readings'] = self._total_readings
            return status


# Process-wide singleton used by the demo control endpoints.
data_replay_service = DataReplayService()