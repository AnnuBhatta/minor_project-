from collections.abc import Mapping
from datetime import timedelta
from statistics import mean

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import VitalSign, Threshold
from .serializers import VitalSignInputSerializer, VitalSignSerializer, ThresholdSerializer
from .inference import run_inference_pipeline

User = get_user_model()


def _resolve_view_patient(request):
    """Resolve which patient's data a read endpoint should return. Defaults
    to the caller. A guardian may pass ?patient_id=<id> to view one of
    their linked patients' dashboards instead."""
    patient_id = request.query_params.get('patient_id')
    if not patient_id or str(patient_id) == str(request.user.id):
        return request.user, None
    target = get_object_or_404(User, id=patient_id)
    if not target.guardians.filter(id=request.user.id).exists():
        return None, Response(
            {'error': 'You do not have permission to view this patient.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return target, None

class VitalSignViewSet(viewsets.ModelViewSet):
    """ViewSet for VitalSign model"""
    queryset = VitalSign.objects.all()
    serializer_class = VitalSignSerializer

class ThresholdViewSet(viewsets.ModelViewSet):
    """ViewSet for Threshold model"""
    queryset = Threshold.objects.all()
    serializer_class = ThresholdSerializer


def _number(value, keys=()):
    """Extract a numeric reading from common JSON payload shapes."""
    if isinstance(value, Mapping):
        for key in (*keys, 'value'):
            candidate = value.get(key)
            if candidate not in (None, ''):
                try:
                    return float(candidate)
                except (TypeError, ValueError):
                    continue
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _blood_pressure(value):
    if isinstance(value, Mapping):
        systolic = _number(value, ('systolic', 'systolic_bp', 'upper'))
        diastolic = _number(value, ('diastolic', 'diastolic_bp', 'lower'))
        return systolic, diastolic
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return _number(value[0]), _number(value[1])
    if isinstance(value, str) and '/' in value:
        systolic, diastolic = value.split('/', 1)
        return _number(systolic), _number(diastolic)
    return None, None


def _risk_category(heart_rate, spo2, systolic_bp, diastolic_bp):
    high_risk = (
        (heart_rate is not None and not 50 <= heart_rate <= 120)
        or (spo2 is not None and spo2 < 90)
        or (systolic_bp is not None and not 80 <= systolic_bp <= 180)
        or (diastolic_bp is not None and not 50 <= diastolic_bp <= 120)
    )
    return 'high' if high_risk else 'low'


def _snapshot(readings):
    """Build the dashboard shape from the latest entry of each vital type."""
    latest_by_type = {}
    for reading in readings:
        latest_by_type.setdefault(reading.vital_type, reading)

    heart_rate = _number(
        latest_by_type.get('heart_rate').value if latest_by_type.get('heart_rate') else None,
        ('heart_rate', 'bpm'),
    )
    spo2 = _number(
        latest_by_type.get('oxygen_saturation').value if latest_by_type.get('oxygen_saturation') else None,
        ('spo2', 'oxygen_saturation', 'oxygen'),
    )
    systolic_bp, diastolic_bp = _blood_pressure(
        latest_by_type.get('blood_pressure').value if latest_by_type.get('blood_pressure') else None,
    )
    timestamps = [reading.timestamp for reading in latest_by_type.values()]

    return {
        'heart_rate': heart_rate,
        'spo2': spo2,
        'oxygen_saturation': spo2,
        'systolic_bp': systolic_bp,
        'diastolic_bp': diastolic_bp,
        'derived_map': round((systolic_bp + 2 * diastolic_bp) / 3, 1)
        if systolic_bp is not None and diastolic_bp is not None
        else None,
        'risk_category': _risk_category(heart_rate, spo2, systolic_bp, diastolic_bp),
        'timestamp': max(timestamps).isoformat() if timestamps else None,
    }


class VitalListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = VitalSignInputSerializer
    pagination_class = None

    def get_queryset(self):
        return VitalSign.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class VitalLatestView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        patient, error = _resolve_view_patient(request)
        if error:
            return error
        readings = list(VitalSign.objects.filter(user=patient).order_by('-timestamp'))
        return Response(_snapshot(readings) if readings else {})


class VitalHistoryView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        patient, error = _resolve_view_patient(request)
        if error:
            return error
        limit = min(max(int(request.query_params.get('limit', 100)), 1), 500)
        readings = VitalSign.objects.filter(user=patient).order_by('-timestamp')[:limit]
        history = []
        for reading in readings:
            entry = _snapshot([reading])
            entry.update({'id': reading.id, 'timestamp': reading.timestamp.isoformat(), 'source': reading.source})
            history.append(entry)
        return Response(history)


class VitalTrendView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        patient, error = _resolve_view_patient(request)
        if error:
            return error
        values = [
            _number(reading.value, ('heart_rate', 'bpm'))
            for reading in VitalSign.objects.filter(user=patient, vital_type='heart_rate')[:14]
        ]
        values = [value for value in values if value is not None]
        if len(values) < 4:
            return Response({
                'trend': 'insufficient_data',
                'message': 'At least four heart-rate readings are needed to calculate a trend.',
            })

        midpoint = len(values) // 2
        recent_average = mean(values[:midpoint])
        previous_average = mean(values[midpoint:])
        if recent_average > 120 or recent_average < 50:
            trend = 'high_risk'
            note = 'Recent heart-rate readings are outside the expected range.'
        elif recent_average - previous_average >= 10:
            trend = 'increasing_risk'
            note = 'Recent heart-rate readings are increasing compared with earlier readings.'
        else:
            trend = 'stable'
            note = 'Recent heart-rate readings are stable compared with earlier readings.'

        return Response({
            'trend': trend,
            'average_heart_rate_recent': round(recent_average, 1),
            'average_heart_rate_previous': round(previous_average, 1),
            'note': note,
        })


class WeeklyReportView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        patient, error = _resolve_view_patient(request)
        if error:
            return error
        readings = list(VitalSign.objects.filter(user=patient)[:500])
        heart_rates = [
            _number(reading.value, ('heart_rate', 'bpm'))
            for reading in readings if reading.vital_type == 'heart_rate'
        ]
        spo2_values = [
            _number(reading.value, ('spo2', 'oxygen_saturation', 'oxygen'))
            for reading in readings if reading.vital_type == 'oxygen_saturation'
        ]
        heart_rates = [value for value in heart_rates if value is not None]
        spo2_values = [value for value in spo2_values if value is not None]
        latest = _snapshot(readings) if readings else None

        return Response({
            'average_heart_rate': round(mean(heart_rates), 1) if heart_rates else None,
            'average_spo2': round(mean(spo2_values), 1) if spo2_values else None,
            'high_risk_readings': sum(reading.is_abnormal for reading in readings),
            'total_readings': len(readings),
            'last_status': latest['risk_category'] if latest else 'no_data',
        })


class DailyChartView(generics.GenericAPIView):
    """
    Powers the caregiver dashboard chart: daily mean + peak heart rate,
    percentage of time spent in high risk, alert markers overlaid on the
    timeline, and an episode-count/duration badge (a "high-risk episode" is
    a run of consecutive high-risk readings).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        patient, error = _resolve_view_patient(request)
        if error:
            return error

        days = min(max(int(request.query_params.get('days', 7)), 1), 31)
        since = timezone.now() - timedelta(days=days)

        readings = list(
            VitalSign.objects.filter(user=patient, timestamp__gte=since)
            .exclude(vital_type__in=['weight', 'ecg'])
            .order_by('timestamp')
        )

        # ---- daily mean + peak heart rate (from raw readings) ---- #
        by_day = {}
        for reading in readings:
            if reading.vital_type != 'heart_rate':
                continue
            hr = _number(reading.value, ('heart_rate', 'bpm'))
            if hr is None:
                continue
            by_day.setdefault(reading.timestamp.date().isoformat(), []).append(hr)
        daily_series = [
            {'date': day, 'mean_heart_rate': round(mean(vals), 1), 'peak_heart_rate': round(max(vals), 1)}
            for day, vals in sorted(by_day.items())
        ]

        # ---- risk-over-time, %time-in-high-risk, episodes ---- #
        # Driven by the same Prediction records that trigger alerts (RF
        # snapshot classification per ingest event), so this chart can never
        # disagree with the alert markers overlaid on it.
        from ml_api.models import Prediction
        from alerts.models import Alert

        predictions = list(
            Prediction.objects.filter(
                user=patient, prediction_type='health_risk', created_at__gte=since,
            ).order_by('created_at')
        )

        timeline = [
            {'timestamp': p.created_at.isoformat(), 'risk_level': p.risk_level, 'risk_score': p.risk_score}
            for p in predictions
        ]

        high_risk_count = sum(1 for p in predictions if p.risk_level == 'high')
        pct_time_high_risk = round(100 * high_risk_count / len(predictions), 1) if predictions else 0.0

        episodes = []
        current_start = current_end = None
        for p in predictions:
            if p.risk_level == 'high':
                if current_start is None:
                    current_start = p.created_at
                current_end = p.created_at
            else:
                if current_start is not None:
                    episodes.append({'start': current_start, 'end': current_end})
                    current_start = None
        if current_start is not None:
            episodes.append({'start': current_start, 'end': current_end})

        episodes_out = [
            {
                'start': ep['start'].isoformat(),
                'end': ep['end'].isoformat(),
                'duration_minutes': round((ep['end'] - ep['start']).total_seconds() / 60, 1),
            }
            for ep in episodes
        ]

        # ---- alert markers to overlay on the chart ---- #
        alert_markers = [
            {'id': a.id, 'timestamp': a.created_at.isoformat(), 'severity': a.severity, 'title': a.title}
            for a in Alert.objects.filter(user=patient, created_at__gte=since).order_by('created_at')
        ]

        return Response({
            'patient_id': patient.id,
            'days': days,
            'daily_series': daily_series,
            'pct_time_high_risk': pct_time_high_risk,
            'episode_count': len(episodes_out),
            'episodes': episodes_out,
            'alert_markers': alert_markers,
            'timeline': timeline,
        })


def _resolve_target_patient(request_user, patient_id):
    """A reading always belongs to a patient. If no patient_id is given, the
    authenticated caller IS the patient (this is how a real watch or the
    simulator would authenticate). A patient_id may be supplied by a
    guardian viewing/feeding data for one of their patients."""
    if not patient_id or str(patient_id) == str(request_user.id):
        return request_user, None
    target = get_object_or_404(User, id=patient_id)
    is_self = target.id == request_user.id
    is_guardian_of_target = target.guardians.filter(id=request_user.id).exists()
    if not (is_self or is_guardian_of_target):
        return None, 'You do not have permission to submit readings for this patient.'
    return target, None


class VitalReadingIngestView(APIView):
    """
    Source-agnostic ingestion endpoint: POST /api/readings/ingest/

    Accepts either a single reading object or a batch. It does not care
    whether the data came from the demo scenario runner (source=simulated)
    or a real device (source=device) -- both are written to the same
    VitalSign table, tagged by `source`, so nothing downstream (inference,
    dashboard, alerts) needs a second code path when a real watch is added
    later.

    Body shapes accepted:
      {"vital_type": "heart_rate", "value": {"heart_rate": 82}, "source": "device"}
      {"readings": [ {...}, {...} ], "patient_id": 4, "source": "simulated"}
      [ {...}, {...} ]   (bare list, same shape as the "readings" case)

    Per-item `patient_id` / `source` override the top-level ones if present.
    Runs the RF + LSTM inference pipeline once per distinct patient touched
    by the request, after all readings in the batch are saved.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        body = request.data
        if isinstance(body, list):
            top_level = {}
            raw_readings = body
        else:
            top_level = body
            raw_readings = body.get('readings', [body]) if 'vital_type' in body or 'readings' in body else body.get('readings', [])

        if not raw_readings:
            return Response({'error': 'No readings supplied.'}, status=status.HTTP_400_BAD_REQUEST)

        default_source = top_level.get('source', 'device')
        default_patient_id = top_level.get('patient_id')
        default_scenario_id = top_level.get('scenario_id')

        created = []
        errors = []
        touched_patients = {}

        for index, item in enumerate(raw_readings):
            patient_id = item.get('patient_id', default_patient_id)
            target_patient, perm_error = _resolve_target_patient(request.user, patient_id)
            if perm_error:
                errors.append({'index': index, 'error': perm_error})
                continue

            payload = {
                'vital_type': item.get('vital_type'),
                'value': item.get('value'),
                'unit': item.get('unit'),
                'device_id': item.get('device_id'),
                'notes': item.get('notes'),
                'source': item.get('source', default_source),
                'scenario_id': item.get('scenario_id', default_scenario_id),
            }
            serializer = VitalSignInputSerializer(data=payload)
            if not serializer.is_valid():
                errors.append({'index': index, 'error': serializer.errors})
                continue

            reading = serializer.save(user=target_patient)

            # Allow the simulator to backdate readings so a sped-up scenario
            # (e.g. "1 simulated hour every few real seconds") still lines
            # up on time-series charts. Optional -- real devices won't send this.
            simulated_timestamp = item.get('timestamp')
            if simulated_timestamp:
                parsed = parse_datetime(simulated_timestamp)
                if parsed:
                    reading.timestamp = parsed
                    reading.save(update_fields=['timestamp'])

            created.append(VitalSignSerializer(reading).data)
            touched_patients[target_patient.id] = target_patient

        inference_results = []
        for patient in touched_patients.values():
            inference_results.append(run_inference_pipeline(patient))

        response_status = status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST
        return Response({
            'created': created,
            'created_count': len(created),
            'errors': errors,
            'inference': inference_results,
        }, status=response_status)
