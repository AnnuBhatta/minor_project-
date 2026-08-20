"""
Runs whenever a new reading (real or simulated) lands via the ingest
endpoint:

  1. Random Forest snapshot classification on the patient's latest reading
     of each vital type.
  2. LSTM trend / early-warning check on the patient's last 10 readings
     (a ~20-minute window at the normal 2-minute cadence).
  3. Routes both through the three-tier alert engine (Tier 1 hard-threshold
     breach fires immediately; Tier 2 needs 3 consecutive high-risk
     readings; Tier 3 trend has a 30-minute cooldown) and delivers any
     triggered alert to the patient + guardians (DB Alert, WebSocket, and
     FCM push with live location for Tier 1).
  4. Records a Prediction audit row for each model run so the dashboard
     charts stay consistent with what triggered alerts.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from ml_api.models import Prediction
from ml_models.alert_delivery import deliver_alert
from ml_models.alert_engine import AlertManager
from ml_models.predictions.service import prediction_service
from ml_models.predictions.lstm_service import lstm_trend_service, DEFAULT_WINDOW_SIZE
from .models import VitalSign

logger = logging.getLogger(__name__)

# The LSTM forecasts the current reading from the previous
# `window_size` readings, so we must fetch window_size + 1 heart-rate readings.
LSTM_WINDOW_SIZE = getattr(lstm_trend_service, 'window_size', DEFAULT_WINDOW_SIZE) + 1


def _latest_by_type(patient):
    latest = {}
    for reading in VitalSign.objects.filter(user=patient).order_by('-timestamp')[:100]:
        latest.setdefault(reading.vital_type, reading)
    return latest


def _number(value, keys):
    if isinstance(value, dict):
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


def _value_at_or_before(patient, vital_type, timestamp):
    reading = (
        VitalSign.objects.filter(user=patient, vital_type=vital_type, timestamp__lte=timestamp)
        .order_by('-timestamp')
        .first()
    )
    return reading


def _build_lstm_window(patient):
    """Uses the patient's last LSTM_WINDOW_SIZE heart_rate readings as the
    tick reference, then forward-fills spo2/blood-pressure from whichever
    reading of that type was most recent at each tick.

    Each row carries the LSTM model's 6 features: heart_rate, oxygen
    saturation, systolic/diastolic blood pressure, Derived_HR (defaulted to
    0.1 -- no per-patient HRV history), and Derived_Pulse_Pressure. Every row
    also carries its `timestamp` so the LSTM keeps the temporal ordering the
    model was trained on.
    """
    hr_readings = list(
        VitalSign.objects.filter(user=patient, vital_type='heart_rate').order_by('-timestamp')[:LSTM_WINDOW_SIZE]
    )
    if len(hr_readings) < LSTM_WINDOW_SIZE:
        return None, len(hr_readings)

    hr_readings.reverse()  # oldest first
    window = []
    for hr_reading in hr_readings:
        heart_rate = _number(hr_reading.value, ('heart_rate', 'bpm'))
        spo2_reading = _value_at_or_before(patient, 'oxygen_saturation', hr_reading.timestamp)
        spo2 = _number(spo2_reading.value, ('spo2', 'oxygen_saturation')) if spo2_reading else None
        bp_reading = _value_at_or_before(patient, 'blood_pressure', hr_reading.timestamp)
        systolic = diastolic = None
        if bp_reading and isinstance(bp_reading.value, dict):
            systolic = _number(bp_reading.value, ('systolic', 'systolic_bp', 'upper'))
            diastolic = _number(bp_reading.value, ('diastolic', 'diastolic_bp', 'lower'))
        window.append({
            'timestamp': hr_reading.timestamp.isoformat(),
            'heart_rate': heart_rate,
            'oxygen_saturation': spo2,
            'systolic_bp': systolic,
            'diastolic_bp': diastolic,
            'derived_hr': 0.1,
            'derived_pulse_pressure': (
                round(systolic - diastolic, 2)
                if systolic is not None and diastolic is not None
                else None
            ),
        })
    return window, len(hr_readings)


def _engine_data(patient, latest_by_type):
    """Flatten the latest reading of each vital type into the six keys the
    alert engine's Tier-1 threshold check uses. These are exactly the model
    features (Heart Rate, Oxygen Saturation, Systolic/Diastolic Blood
    Pressure, Derived_HR, Derived_Pulse_Pressure)."""
    data = {}

    hr = latest_by_type.get('heart_rate')
    if hr is not None:
        value = _number(hr.value, ('heart_rate', 'bpm'))
        if value is not None:
            data['heart_rate'] = value

    spo2 = latest_by_type.get('oxygen_saturation')
    if spo2 is not None:
        value = _number(spo2.value, ('spo2', 'oxygen_saturation'))
        if value is not None:
            data['oxygen_saturation'] = value

    systolic = diastolic = None
    bp = latest_by_type.get('blood_pressure')
    if bp is not None and isinstance(bp.value, dict):
        systolic = _number(bp.value, ('systolic', 'systolic_bp', 'upper'))
        diastolic = _number(bp.value, ('diastolic', 'diastolic_bp', 'lower'))
        if systolic is not None:
            data['blood_pressure_systolic'] = systolic
        if diastolic is not None:
            data['blood_pressure_diastolic'] = diastolic

    # Derived_HR has no per-patient history at inference time, so it uses the
    # same training-set default (0.1) as the RF/LSTM services.
    data['derived_hr'] = 0.1
    if systolic is not None and diastolic is not None:
        data['derived_pulse_pressure'] = round(systolic - diastolic, 2)

    return data


def _rf_engine_prediction(rf_result):
    """Shapes the RF snapshot result into what the engine's Tier-2 logic
    expects: is_anomaly + confidence."""
    if 'error' in rf_result or rf_result.get('risk_level') != 'high':
        return {'is_anomaly': False, 'confidence': 0.0}
    return {
        'is_anomaly': True,
        'confidence': rf_result.get('probability', {}).get('high_risk', 0.0),
    }


def _broadcast(patient, payload):
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            f"user_{patient.id}_vitals",
            {'type': 'vitals_update', **payload},
        )
    except Exception:
        logger.exception('Failed to broadcast vitals update for patient %s', patient.id)


def run_inference_pipeline(patient):
    """
    Called once per ingest request, after the batch of readings for `patient`
    has been saved. Returns a dict summarizing what ran, for the ingest
    response payload.
    """
    result = {'patient_id': patient.id, 'random_forest': None, 'lstm_trend': None, 'alerts_created': []}

    # ---- 1. Random Forest snapshot classification -------------------- #
    latest_by_type = _latest_by_type(patient)
    features, warnings = prediction_service.build_features_from_vitals(patient, latest_by_type)
    rf_result = prediction_service.predict_health_risk(features)
    result['random_forest'] = rf_result
    result['random_forest_assumptions'] = warnings

    if 'error' not in rf_result:
        Prediction.objects.create(
            user=patient,
            prediction_type='health_risk',
            input_data=features,
            result=rf_result,
            risk_score=rf_result.get('risk_score', 0),
            risk_level=rf_result.get('risk_level', 'unknown'),
        )

    # ---- 2. LSTM trend / early-warning check -------------------------- #
    window, available = _build_lstm_window(patient)
    if window is None:
        lstm_result = {
            'trend': 'insufficient_data',
            'window_size': available,
            'required_window_size': LSTM_WINDOW_SIZE,
        }
    else:
        lstm_result = lstm_trend_service.predict_trend(window)
    result['lstm_trend'] = lstm_result

    if lstm_result.get('trend') == 'early_warning':
        Prediction.objects.create(
            user=patient,
            prediction_type='trend_early_warning',
            input_data={'window': window},
            result=lstm_result,
            risk_score=round(lstm_result.get('probability', 0) * 100, 2),
            risk_level='high',
        )

    # ---- 3. Three-tier debounced alert engine ------------------------- #
    engine_data = _engine_data(patient, latest_by_type)
    alerts = []
    if engine_data:
        alerts = AlertManager.process_reading(
            patient.id,
            engine_data,
            rf_prediction=_rf_engine_prediction(rf_result),
            lstm_prediction=lstm_result,
        )

    result['tiers_triggered'] = [a.get('tier') for a in alerts]
    for alert in alerts:
        alert_id = deliver_alert(patient, alert)
        if alert_id is not None:
            result['alerts_created'].append(alert_id)

    _broadcast(patient, {
        'random_forest': rf_result,
        'lstm_trend': lstm_result,
        'alerts_created': result['alerts_created'],
    })

    return result
