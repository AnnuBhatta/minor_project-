import json
from datetime import datetime, timedelta
from collections import deque
import logging
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)
User = get_user_model()


def _fmt_value(value, threshold):
    """Format a vital value with its unit for alert messages."""
    unit = threshold.get('unit', '')
    if unit == '%':
        return f"{value}%"
    return f"{value} {unit}".strip()


def _normal_range(threshold):
    """Human-readable normal range from a threshold dict (min/max)."""
    unit = threshold.get('unit', '')
    low, high = threshold.get('min'), threshold.get('max')
    if low is not None and high is not None:
        return f"normal {low}-{high} {unit}".strip()
    if low is not None:
        return f"normal ≥{low} {unit}".strip()
    if high is not None:
        return f"normal ≤{high} {unit}".strip()
    return 'normal'

# ============================================================
# Tier 1 - configurable critical thresholds (pure rule-based, no ML)
# ============================================================
# Display labels keyed by the same snake_case keys the ingest pipeline uses.
TIER1_PARAMETER_LABELS = {
    'heart_rate': 'Heart Rate',
    'oxygen_saturation': 'Oxygen Saturation',
    'blood_pressure_systolic': 'Systolic Blood Pressure',
    'blood_pressure_diastolic': 'Diastolic Blood Pressure',
    'derived_pulse_pressure': 'Derived Pulse Pressure',
}

# Units: Heart Rate bpm, Oxygen Saturation %, Systolic/Diastolic BP mmHg,
# Derived Pulse Pressure mmHg. `max: None` means no critical upper bound.
TIER1_CRITICAL_THRESHOLDS = {
    'heart_rate': {'min': 40, 'max': 140, 'unit': 'bpm'},
    'oxygen_saturation': {'min': 90, 'max': None, 'unit': '%'},
    'blood_pressure_systolic': {'min': 80, 'max': 180, 'unit': 'mmHg'},
    'blood_pressure_diastolic': {'min': 50, 'max': 120, 'unit': 'mmHg'},
    'derived_pulse_pressure': {'min': 20, 'max': 70, 'unit': 'mmHg'},
}

# Rule (b): fire a "multi-parameter critical" Tier 1 alert when this many
# parameters are simultaneously outside their critical range.
TIER1_MULTI_PARAMETER_MIN_COUNT = 3

class AlertEngine:
    """
    Three-tier alert system with debouncing

    Tier 1: Emergency - Hard threshold breach (Immediate)
    Tier 2: Health Alert - RF predicts high risk (Debounced: 3 consecutive readings)
    Tier 3: Trend Alert - LSTM checks the last hour; only evaluated after
            Tier 2 fires (Cooldown: 30 min). When the last-hour condition is
            worst (severe deterioration), it escalates to a Tier 1 EMERGENCY.
    """
    
    def __init__(self, user_id):
        self.user_id = user_id
        self.consecutive_high_risk_count = 0
        self.tier2_last_fired = None  # Timestamp of last Tier 2 alert
        self.tier3_last_fired = None  # Timestamp of last Tier 3 alert
        self.tier3_cooldown_minutes = 30
        
        # Store recent readings for LSTM (last hour)
        self.recent_readings = deque(maxlen=30)  # 30 readings at 2-min interval = 1 hour
        
        # Load thresholds from config
        self.load_thresholds()
    
    def load_thresholds(self):
        """Load Tier 1 critical thresholds (tunable module constants).

        Keys map onto the vitals the ingest pipeline supplies; thresholds
        and the multi-parameter minimum count are defined once at module
        level (TIER1_CRITICAL_THRESHOLDS / TIER1_MULTI_PARAMETER_MIN_COUNT)
        so they can be tuned without touching the rule logic.
        """
        self.critical_thresholds = TIER1_CRITICAL_THRESHOLDS
        self.tier1_multi_parameter_min_count = TIER1_MULTI_PARAMETER_MIN_COUNT

    def check_tier1_emergency(self, data):
        """
        Tier 1: Critical threshold breach. Fires immediately, no debounce, no ML.

        Single deterministic rule (multi_parameter_count): an emergency only
        fires when TIER1_MULTI_PARAMETER_MIN_COUNT or more parameters are
        simultaneously outside their critical range -> "multi-parameter
        critical" alert.

        Returns a list with at most one alert dict, or an empty list when no
        emergency. The alert carries the breached parameters so the payload
        can explain exactly why it fired.
        """
        breaches = self._evaluate_tier1_breaches(data)
        if len(breaches) < self.tier1_multi_parameter_min_count:
            return []

        labels = [b['label'] for b in breaches]
        reason_parts = [
            f"{b['label']}={_fmt_value(b['value'], b['threshold'])} "
            f"({_normal_range(b['threshold'])})"
            for b in breaches
        ]
        return [{
            'triggered': True,
            'tier': 1,
            'severity': 'critical',
            'rule': 'multi_parameter_count',
            'breaches': [
                {
                    'parameter': b['parameter'],
                    'parameter_label': b['label'],
                    'value': b['value'],
                    'threshold': b['threshold'],
                    'reason': b['reason'],
                    'direction': b['direction'],
                }
                for b in breaches
            ],
            'breach_count': len(breaches),
            'minimum_count': self.tier1_multi_parameter_min_count,
            'total_parameters': len(TIER1_CRITICAL_THRESHOLDS),
            'breached_parameters': labels,
            'breached_parameter_keys': [b['parameter'] for b in breaches],
            'message': (
                f"[EMERGENCY] {len(breaches)} of {len(TIER1_CRITICAL_THRESHOLDS)} "
                f"vitals out of range: {', '.join(reason_parts)}. "
                f"IMMEDIATE MEDICAL ATTENTION REQUIRED!"
            ),
        }]

    def _evaluate_tier1_breaches(self, data):
        """Return a list of breach dicts (parameter, label, value, threshold,
        reason, direction) for every monitored parameter currently outside
        its critical range. Pure rule-based and deterministic."""
        breaches = []
        for key, threshold in self.critical_thresholds.items():
            value = data.get(key)
            if value is None:
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue

            label = TIER1_PARAMETER_LABELS.get(key, key.replace('_', ' ').title())
            unit = threshold.get('unit', '')
            min_value = threshold.get('min')
            max_value = threshold.get('max')

            def _fmt(num):
                if unit == '%':
                    return f"{num}%"
                return f"{num} {unit}".strip()

            if min_value is not None and value < min_value:
                breaches.append({
                    'parameter': key,
                    'label': label,
                    'value': value,
                    'threshold': threshold,
                    'reason': f"{label} below {_fmt(min_value)}",
                    'direction': 'low',
                })
            elif max_value is not None and value > max_value:
                breaches.append({
                    'parameter': key,
                    'label': label,
                    'value': value,
                    'threshold': threshold,
                    'reason': f"{label} above {_fmt(max_value)}",
                    'direction': 'high',
                })

        return breaches
    
    def check_tier2_health_alert(self, data, rf_prediction):
        """
        Tier 2: RF predicts high risk
        Debounced: Requires 3 consecutive readings
        """
        # Reset counter if RF says normal
        if not rf_prediction.get('is_anomaly', False):
            self.consecutive_high_risk_count = 0
            return {'triggered': False}
        
        # Increment counter for consecutive high risk
        self.consecutive_high_risk_count += 1
        
        # Check if we have 3 consecutive readings
        if self.consecutive_high_risk_count >= 3:
            # Reset counter to prevent continuous firing
            self.consecutive_high_risk_count = 0
            self.tier2_last_fired = datetime.now()

            # Build a readable breakdown of the last 3 high-risk readings so
            # the reason shows exactly which values tripped the rule.
            recent = list(self.recent_readings)
            recent3 = [d['data'] for d in recent[-3:]]
            readings_desc = ', '.join(
                f"Reading {i + 1}: HR={d.get('heart_rate')} bpm, "
                f"SpO2={d.get('oxygen_saturation')}%, "
                f"BP={d.get('blood_pressure_systolic')}/{d.get('blood_pressure_diastolic')}"
                for i, d in enumerate(recent3)
            )
            confidence = rf_prediction.get('confidence', 0) or 0

            return {
                'triggered': True,
                'tier': 2,
                'severity': 'high',
                'confidence': confidence,
                'consecutive_readings': 3,
                'message': (
                    f"[ALERT] 3 consecutive high-risk readings detected by the "
                    f"RF model. {readings_desc}. "
                    f"Vitals indicate elevated risk ({confidence * 100:.0f}% confidence)."
                ),
            }

        return {'triggered': False}
    
    def _record_trend_reading(self, data):
        """Keep a rolling window of recent readings so the LSTM / trend check
        always has the last ~hour of data when the Tier 2 gate opens."""
        self.recent_readings.append({
            'timestamp': datetime.now(),
            'data': data
        })

    def check_tier3_trend_alert(self, data, lstm_prediction=None):
        """
        Tier 3: LSTM detects sustained deterioration over the last hour.
        Gated: only evaluated after Tier 2 fires (3 consecutive RF high-risk
        readings). Readings are recorded every cycle by process_reading, so
        the trend window stays fresh. Cooldown: 30 minutes before firing again.

        Escalation: when the last-hour condition is *worst* (LSTM forecast
        error far beyond its warning threshold, or several vitals worsening at
        once), the trend alert escalates to a full Tier 1 EMERGENCY so a
        guardian sees an emergency event, not just a "worth checking in" note.
        """
        # Check cooldown
        if self.tier3_last_fired:
            cooldown_elapsed = (datetime.now() - self.tier3_last_fired).total_seconds() / 60
            if cooldown_elapsed < self.tier3_cooldown_minutes:
                return {'triggered': False, 'cooldown': True}
        
        # Need at least 10 readings (20 minutes) for trend analysis
        if len(self.recent_readings) < 10:
            return {'triggered': False}
        
        # Prefer the LSTM's early-warning signal when available; otherwise
        # fall back to the internal first-third vs last-third trend check.
        if lstm_prediction and lstm_prediction.get('trend') == 'early_warning':
            trend_result = {
                'is_deteriorating': True,
                'source': 'lstm',
                'trend': lstm_prediction.get('trend'),
                'probability': lstm_prediction.get('probability'),
                'error': lstm_prediction.get('error'),
                'threshold': lstm_prediction.get('threshold'),
                'watch_threshold': lstm_prediction.get('watch_threshold'),
                'window_size': lstm_prediction.get('window_size'),
            }
        else:
            trend_result = self._analyze_trend()
        
        if trend_result['is_deteriorating']:
            self.tier3_last_fired = datetime.now()
            recent = list(self.recent_readings)
            start = recent[0]['data'] if recent else {}
            end = recent[-1]['data'] if recent else {}

            if self._is_worst_trend(trend_result):
                # Escalate to a full EMERGENCY (same delivery path as a Tier 1
                # hard-threshold breach: EmergencyEvent + emergency location).
                return {
                    'triggered': True,
                    'tier': 1,
                    'severity': 'critical',
                    'rule': 'lstm_trend_escalation',
                    'trend': trend_result,
                    'message': (
                        f"[EMERGENCY] LSTM confirmed the last hour is trending "
                        f"dangerously: HR rose from {start.get('heart_rate')} to "
                        f"{end.get('heart_rate')} bpm, SpO2 dropped from "
                        f"{start.get('oxygen_saturation')}% to "
                        f"{end.get('oxygen_saturation')}%, BP rose from "
                        f"{start.get('blood_pressure_systolic')}/"
                        f"{start.get('blood_pressure_diastolic')} to "
                        f"{end.get('blood_pressure_systolic')}/"
                        f"{end.get('blood_pressure_diastolic')}. "
                        f"IMMEDIATE MEDICAL ATTENTION REQUIRED!"
                    ),
                }

            return {
                'triggered': True,
                'tier': 3,
                'severity': 'medium',
                'trend': trend_result,
                'message': (
                    f"[TREND] Sustained deterioration detected over the last "
                    f"hour. HR increased from {start.get('heart_rate')} to "
                    f"{end.get('heart_rate')} bpm, SpO2 dropped from "
                    f"{start.get('oxygen_saturation')}% to "
                    f"{end.get('oxygen_saturation')}%, BP rose from "
                    f"{start.get('blood_pressure_systolic')}/"
                    f"{start.get('blood_pressure_diastolic')} to "
                    f"{end.get('blood_pressure_systolic')}/"
                    f"{end.get('blood_pressure_diastolic')}. Worth checking in."
                ),
            }
        
        return {'triggered': False}

    def _is_worst_trend(self, trend_result):
        """
        True when the last-hour deterioration is severe enough to escalate to
        an EMERGENCY ("worst" condition):

          - LSTM path: the forecast error is far beyond its warning threshold
            (>= 1.25x), or the early-warning probability is >= 0.85.
          - Internal fallback: two or more vitals are deteriorating at once.
        """
        if trend_result.get('source') == 'lstm':
            error = trend_result.get('error')
            threshold = trend_result.get('threshold')
            if error is not None and threshold:
                if error >= 1.25 * threshold:
                    return True
            if (trend_result.get('probability') or 0) >= 0.85:
                return True
            return False
        return len(trend_result.get('deteriorating_params', [])) >= 2
    
    def _analyze_trend(self):
        """
        Analyze trend in recent readings
        Returns True if sustained deterioration detected
        """
        if len(self.recent_readings) < 10:
            return {'is_deteriorating': False}
        
        # Track the same six model features used by the RF/LSTM.
        parameters = [
            'heart_rate',
            'oxygen_saturation',
            'blood_pressure_systolic',
            'blood_pressure_diastolic',
            'derived_hr',
            'derived_pulse_pressure',
        ]
        trends = {}
        
        for param in parameters:
            values = []
            timestamps = []
            for reading in self.recent_readings:
                if param in reading['data']:
                    values.append(reading['data'][param])
                    timestamps.append(reading['timestamp'])
            
            if len(values) >= 10:
                # Simple trend: compare first third vs last third
                third = len(values) // 3
                first_third = values[:third]
                last_third = values[-third:]
                
                first_avg = sum(first_third) / len(first_third)
                last_avg = sum(last_third) / len(last_third)
                
                # Check if deteriorating (increasing for most parameters)
                deterioration = last_avg - first_avg
                
                # Define what "deterioration" means for each parameter
                if param == 'heart_rate' and deterioration > 15:
                    trends[param] = {'deteriorating': True, 'change': deterioration}
                elif param == 'blood_pressure_systolic' and deterioration > 20:
                    trends[param] = {'deteriorating': True, 'change': deterioration}
                elif param == 'blood_pressure_diastolic' and deterioration > 15:
                    trends[param] = {'deteriorating': True, 'change': deterioration}
                elif param == 'oxygen_saturation' and deterioration < -3:
                    trends[param] = {'deteriorating': True, 'change': deterioration}
                elif param == 'derived_hr' and deterioration < -0.03:
                    trends[param] = {'deteriorating': True, 'change': deterioration}
                elif param == 'derived_pulse_pressure' and abs(deterioration) > 20:
                    trends[param] = {'deteriorating': True, 'change': deterioration}
                else:
                    trends[param] = {'deteriorating': False, 'change': deterioration}
        
        # Check if any parameter shows deterioration
        deteriorating_params = [p for p, t in trends.items() if t['deteriorating']]
        
        return {
            'is_deteriorating': len(deteriorating_params) > 0,
            'deteriorating_params': deteriorating_params,
            'trends': trends
        }
    
    def process_reading(self, data, rf_prediction=None, lstm_prediction=None):
        """
        Main entry point: Process a new reading and determine alerts.
        Flow (matching the tier diagram):
            Tier 1 (immediate) -> if fired, stop
            Tier 2 (RF, 3 consecutive) -> only when this fires do we continue
            Tier 3 (LSTM trend) -> evaluated only after Tier 2 fires
        """
        alerts = []
        
        # Step 1: Check Tier 1 - Emergency (Highest Priority)
        tier1_alerts = self.check_tier1_emergency(data)
        if tier1_alerts:
            # If Tier 1 fires, skip Tier 2 and Tier 3 for this cycle
            logger.info(f"🚨 TIER 1 EMERGENCY for user {self.user_id}")
            alerts.extend(tier1_alerts)
            return alerts

        # Always keep the trend window fresh so Tier 3 has data when the
        # Tier 2 gate opens.
        self._record_trend_reading(data)

        # Step 2: Check Tier 2 - Health Alert (Debounced RF)
        tier2_triggered = False
        if rf_prediction:
            tier2_result = self.check_tier2_health_alert(data, rf_prediction)
            if tier2_result['triggered']:
                logger.info(f"⚠️ TIER 2 ALERT for user {self.user_id} (3 consecutive)")
                alerts.append(tier2_result)
                tier2_triggered = True

        # Step 3: Check Tier 3 - Trend Alert (LSTM with cooldown), ONLY after
        # Tier 2 fires (3 consecutive high-risk readings).
        if tier2_triggered:
            tier3_result = self.check_tier3_trend_alert(data, lstm_prediction)
            if tier3_result['triggered']:
                logger.info(f"📉 TIER 3 TREND for user {self.user_id}")
                alerts.append(tier3_result)
        
        # Log debouncing status
        if rf_prediction and rf_prediction.get('is_anomaly', False):
            logger.debug(f"User {self.user_id}: High risk count = {self.consecutive_high_risk_count}/3")
        
        return alerts


class AlertManager:
    """
    Manages alert engines for multiple users
    """
    _instances = {}
    
    @classmethod
    def get_engine(cls, user_id):
        """Get or create an alert engine for a user"""
        if user_id not in cls._instances:
            cls._instances[user_id] = AlertEngine(user_id)
        return cls._instances[user_id]
    
    @classmethod
    def clear_engine(cls, user_id):
        """Clear a user's alert engine (useful for testing)"""
        if user_id in cls._instances:
            del cls._instances[user_id]
    
    @classmethod
    def process_reading(cls, user_id, data, rf_prediction=None, lstm_prediction=None):
        """Process a reading through the user's alert engine"""
        engine = cls.get_engine(user_id)
        return engine.process_reading(data, rf_prediction, lstm_prediction)


# Singleton instance
alert_manager = AlertManager()