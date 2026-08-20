"""
Runtime wrapper around the trained single-layer LSTM model
(lstm_single_layer.keras + its lstm_single_*.joblib sidecars).

The model is a single-layer LSTM *forecaster* (architecture LSTM 32 ->
Dense 16 -> Dense 6) that reads a 60-step window of 6 vitals and predicts the
next reading's 6 values (regression output - one unit per feature, no
sigmoid). The app uses it as an anomaly / early-warning detector:

    1. Take the last 60 readings *before* the current one as the model input.
    2. The model forecasts what the current reading "should" be.
    3. Measure the forecast error (RMSE across the 6 standardized features)
       between the predicted and the actual current reading.
    4. If the error exceeds the trained threshold (the configured percentile
       of the validation errors, read from lstm_single_config.joblib /
       lstm_single_threshold.joblib -- currently the 80th percentile,
       ~0.86), the vitals are behaving unexpectedly ->
       trend = 'early_warning'. Below the watch level -> 'stable'; the
       band between the two -> 'watch'.

The window size, threshold and watch level are loaded from the files saved
next to the model (lstm_single_config.joblib / lstm_single_threshold.joblib),
with a watch level derived from the threshold when no validation-error file is
present. Inputs are standardized with lstm_feature_scaler.joblib.
"""
import logging
import os
from pathlib import Path

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')

import joblib
import numpy as np

logger = logging.getLogger(__name__)

try:
    from tensorflow import keras
    _HAS_TF = True
except ImportError:  # pragma: no cover - only when TF isn't installed
    keras = None
    _HAS_TF = False

# Keys used to pull values out of the reading dicts passed to predict_trend().
FEATURE_ORDER = [
    'heart_rate',
    'oxygen_saturation',
    'systolic_bp',
    'diastolic_bp',
    'derived_hr',
    'derived_pulse_pressure',
]
# Model column order (must match lstm_feature_scaler.joblib column order and
# the order the model was trained on).
FEATURE_COLUMNS = [
    'Heart Rate',
    'Oxygen Saturation',
    'Systolic Blood Pressure',
    'Diastolic Blood Pressure',
    'Derived_HR',
    'Derived_Pulse_Pressure',
]
# Missing-channel fill defaults, keyed by FEATURE_ORDER entry.
DEFAULTS = {
    'heart_rate': 75.0,
    'oxygen_saturation': 97.0,
    'systolic_bp': 115.0,
    'diastolic_bp': 75.0,
    'derived_hr': 0.1,
    'derived_pulse_pressure': 40.0,
}
# Fallbacks used only when the saved config / threshold sidecars are missing.
DEFAULT_WINDOW_SIZE = 60
DEFAULT_HIGH_RISK_THRESHOLD = 1.23
DEFAULT_WATCH_THRESHOLD = 1.05


class LSTMTrendService:
    _instance = None
    _model = None
    _scaler = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        base_dir = Path(__file__).resolve().parent.parent
        model_path = base_dir / 'models' / 'lstm_single_layer.keras'
        config_path = base_dir / 'models' / 'lstm_single_config.joblib'
        threshold_path = base_dir / 'models' / 'lstm_single_threshold.joblib'
        val_errors_path = base_dir / 'models' / 'lstm_single_val_errors.joblib'
        scaler_path = base_dir / 'scalers' / 'lstm_feature_scaler.joblib'

        self.window_size = DEFAULT_WINDOW_SIZE
        self.threshold = DEFAULT_HIGH_RISK_THRESHOLD
        self.watch_threshold = DEFAULT_WATCH_THRESHOLD

        if not model_path.exists():
            logger.warning(
                'LSTM weights not found at %s. Train or add the model to enable '
                'trend/early-warning predictions.',
                model_path,
            )
            self._model = None
            return
        if not _HAS_TF:
            logger.warning('tensorflow is not installed; LSTM trend service disabled.')
            self._model = None
            return
        try:
            self._model = keras.models.load_model(model_path, compile=False)
            logger.info('Loaded LSTM trend model from %s', model_path)
        except Exception:
            logger.exception('Failed to load LSTM trend model')
            self._model = None
            return

        # Sidecar tuning: window size, high-risk threshold, watch threshold.
        try:
            cfg = joblib.load(config_path) or {}
            self.window_size = int(cfg.get('context_window', DEFAULT_WINDOW_SIZE))
        except Exception:
            logger.warning('Could not read LSTM config; using defaults')
        try:
            self.threshold = float(joblib.load(threshold_path))
        except Exception:
            pass
        # Watch level: prefer a stored validation-error percentile if a
        # val-errors file is present; otherwise derive the watch level as 85%
        # of the high-risk threshold (the single-layer model ships without a
        # val-errors file, so this keeps a softer "watch" band below the
        # early-warning threshold).
        try:
            errors = np.asarray(joblib.load(val_errors_path)).ravel()
            if errors.size:
                self.watch_threshold = float(np.percentile(errors, 90))
        except Exception:
            if self.threshold > 0:
                self.watch_threshold = round(self.threshold * 0.85, 4)
            else:
                self.watch_threshold = DEFAULT_WATCH_THRESHOLD

        if scaler_path.exists():
            try:
                self._scaler = joblib.load(scaler_path)
                logger.info('Loaded LSTM feature scaler')
            except Exception:
                logger.exception('Failed to load LSTM feature scaler')
                self._scaler = None

    @property
    def is_ready(self):
        return self._model is not None

    @property
    def required_readings(self):
        # The model needs `window_size` inputs plus the current reading it is
        # validated against.
        return self.window_size + 1

    def _standardize(self, arr2d):
        """arr2d: (N, 6) raw array -> (N, 6) standardized with the scaler."""
        flat = np.asarray(arr2d, dtype=float).reshape(-1, 6)
        if self._scaler is not None:
            try:
                import pandas as pd
                flat = self._scaler.transform(pd.DataFrame(flat, columns=FEATURE_COLUMNS))
            except ImportError:
                flat = self._scaler.transform(flat)
        return flat

    def _fill_missing(self, raw_window, raw_actual):
        """Replace NaN channels with the column mean or a normal default."""
        for col in range(raw_window.shape[1]):
            col_vals = raw_window[:, col]
            mask = np.isnan(col_vals)
            if mask.all():
                raw_window[:, col] = DEFAULTS[FEATURE_ORDER[col]]
            elif mask.any():
                raw_window[mask, col] = np.nanmean(col_vals)
            if np.isnan(raw_actual[col]):
                raw_actual[col] = DEFAULTS[FEATURE_ORDER[col]]

    def predict_trend(self, readings):
        """
        readings: list of dicts (oldest first) with keys among
                  heart_rate / oxygen_saturation / systolic_bp / diastolic_bp
                  / derived_hr / derived_pulse_pressure (a `timestamp` key is
                  allowed and ignored by the model). Missing values are
                  forward/backward filled.

        Returns None if there is not enough data or the model isn't loaded,
        otherwise a dict with trend / probability / error / threshold.
        """
        if not self.is_ready:
            return {'error': 'LSTM model not loaded', 'ready': False}

        required = self.required_readings
        if len(readings) < required:
            return {
                'trend': 'insufficient_data',
                'window_size': len(readings),
                'required_window_size': required,
            }

        # 60 readings before the current one are the model input; the newest
        # reading is the "actual" the forecast is compared against.
        window_readings = readings[-(self.window_size + 1):-1]
        actual_reading = readings[-1]

        raw_window = np.array(
            [[r.get(f) for f in FEATURE_ORDER] for r in window_readings],
            dtype=float,
        )
        raw_actual = np.array(
            [actual_reading.get(f) for f in FEATURE_ORDER],
            dtype=float,
        )
        self._fill_missing(raw_window, raw_actual)

        window_std = self._standardize(raw_window)          # (60, 6)
        actual_std = self._standardize(raw_actual.reshape(1, -1))[0]  # (6,)

        predicted = np.asarray(
            self._model.predict(window_std[np.newaxis, :, :], verbose=0)
        )[0]  # (6,)

        # Forecast error = RMSE across the 6 standardized features.
        error = float(np.sqrt(np.mean((predicted - actual_std) ** 2)))

        if error >= self.threshold:
            trend = 'early_warning'
        elif error >= self.watch_threshold:
            trend = 'watch'
        else:
            trend = 'stable'

        denom = self.threshold - self.watch_threshold
        if denom > 0:
            probability = min(1.0, max(0.0, (error - self.watch_threshold) / denom))
        else:
            probability = min(1.0, error / max(self.threshold, 1e-6))

        return {
            'trend': trend,
            'probability': round(probability, 4),
            'high_risk_probability': round(probability, 4),
            'error': round(error, 4),
            'threshold': round(self.threshold, 4),
            'watch_threshold': round(self.watch_threshold, 4),
            'window_size': len(window_readings),
            'model_used': 'lstm_single_layer',
        }


lstm_trend_service = LSTMTrendService()