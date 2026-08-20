try:
    import joblib
    import numpy as np
except ImportError:
    joblib = None
    np = None
from pathlib import Path
import json
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

# Model feature columns (must match rf_risk_model.joblib.feature_names_in_).
# Internal API keys map onto the exact column names the model was trained on.
MODEL_FEATURE_COLUMNS = [
    'Heart Rate',
    'Oxygen Saturation',
    'Systolic Blood Pressure',
    'Diastolic Blood Pressure',
    'Derived_HR',
    'Derived_Pulse_Pressure',
]

FEATURE_KEY_TO_COLUMN = {
    'heart_rate': 'Heart Rate',
    'oxygen_saturation': 'Oxygen Saturation',
    'systolic_bp': 'Systolic Blood Pressure',
    'diastolic_bp': 'Diastolic Blood Pressure',
    'derived_hr': 'Derived_HR',
    'derived_pulse_pressure': 'Derived_Pulse_Pressure',
}

DERIVED_HR_DEFAULT = 0.1  # no patient history available at inference time


class HealthPredictionService:
    """Service for making predictions using trained ML models"""
    
    _instance = None
    _models = {}
    _scalers = {}
    _label_encoder = None
    _feature_config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HealthPredictionService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Load models and configurations"""
        try:
            # Get paths
            base_dir = Path(__file__).resolve().parent.parent
            models_dir = base_dir / 'models'
            scalers_dir = base_dir / 'scalers'
            features_dir = base_dir / 'features'
            
            # Create directories if they don't exist
            models_dir.mkdir(parents=True, exist_ok=True)
            scalers_dir.mkdir(parents=True, exist_ok=True)
            features_dir.mkdir(parents=True, exist_ok=True)
            
            # Load feature configuration
            config_path = features_dir / 'feature_config.json'
            if config_path.exists():
                with open(config_path, 'r') as f:
                    self._feature_config = json.load(f)
            else:
                # Create default config
                self._feature_config = {
                    "risk_features": MODEL_FEATURE_COLUMNS
                }
                with open(config_path, 'w') as f:
                    json.dump(self._feature_config, f, indent=2)
            
            if joblib is None or np is None:
                logger.warning('ML dependencies are unavailable; prediction models will not be loaded.')
                return

            # Load all models
            model_files = list(models_dir.glob('*.joblib'))
            if not model_files:
                logger.info('No model files found. Place trained models in %s.', models_dir)
            else:
                for model_file in model_files:
                    model_name = model_file.stem
                    try:
                        obj = joblib.load(model_file)
                        # Only objects that can actually predict are models;
                        # skip sidecar artifacts (configs, thresholds, arrays)
                        # that happen to live in the same directory.
                        if not hasattr(obj, 'predict'):
                            logger.debug('Skipping %s (not a prediction model)', model_name)
                            continue
                        self._models[model_name] = obj
                        logger.info('Loaded model: %s', model_name)
                    except Exception as e:
                        logger.warning('Failed to load model %s: %s', model_name, e)
            
            # Load scalers
            scaler_files = list(scalers_dir.glob('*.joblib'))
            for scaler_file in scaler_files:
                scaler_name = scaler_file.stem
                try:
                    self._scalers[scaler_name] = joblib.load(scaler_file)
                    logger.info('Loaded scaler: %s', scaler_name)
                except Exception as e:
                    logger.warning('Failed to load scaler %s: %s', scaler_name, e)

            # Load the label encoder ("Low Risk"=0 / "High Risk"=1)
            encoders_dir = base_dir / 'encoders'
            encoder_path = encoders_dir / 'label_encoder.joblib'
            if encoder_path.exists():
                try:
                    self._label_encoder = joblib.load(encoder_path)
                    logger.info('Loaded label encoder: %s', list(getattr(self._label_encoder, 'categories_', getattr(self._label_encoder, 'classes_', [])))[0])
                except Exception as e:
                    logger.warning('Failed to load label encoder: %s', e)
            
            logger.info('ML service initialized. Models loaded: %s', list(self._models.keys()))
            
        except Exception as e:
            logger.exception('Failed to initialize ML service: %s', e)
    
    def _feature_vector(self, features):
        """
        Build the model's feature vector (in MODEL_FEATURE_COLUMNS order) from
        a dict that may use either the snake_case internal keys
        (heart_rate, systolic_bp, ...) or the model's own column names.

        Derived_HR is defaulted to 0.1 (no per-patient HRV history yet);
        Derived_Pulse_Pressure is computed as Systolic - Diastolic whenever
        both pressures are available.
        """
        def _value(features, key, column, *aliases):
            value = features.get(key, features.get(column, 0))
            for alias in aliases:
                if value in (None, 0):
                    value = features.get(alias, value)
            if value in (None, ''):
                value = 0
            return float(value)

        systolic = _value(
            features, 'systolic_bp', 'Systolic Blood Pressure',
            'blood_pressure_systolic', 'systolic',
        )
        diastolic = _value(
            features, 'diastolic_bp', 'Diastolic Blood Pressure',
            'blood_pressure_diastolic', 'diastolic',
        )

        values = {
            'Heart Rate': _value(features, 'heart_rate', 'Heart Rate'),
            'Oxygen Saturation': _value(features, 'oxygen_saturation', 'Oxygen Saturation'),
            'Systolic Blood Pressure': systolic,
            'Diastolic Blood Pressure': diastolic,
            'Derived_HR': _value(features, 'derived_hr', 'Derived_HR') or DERIVED_HR_DEFAULT,
            'Derived_Pulse_Pressure': (
                _value(features, 'derived_pulse_pressure', 'Derived_Pulse_Pressure')
                or (round(systolic - diastolic, 2) if systolic and diastolic else 0.0)
            ),
        }
        try:
            import pandas as pd
            return pd.DataFrame([[values[col] for col in MODEL_FEATURE_COLUMNS]], columns=MODEL_FEATURE_COLUMNS)
        except ImportError:
            return np.array([[values[col] for col in MODEL_FEATURE_COLUMNS]], dtype=float)

    def predict_health_risk(self, features):
        """
        Predict health risk using the trained Random Forest model
        (Smartwatch_RandomForest_Minor_Project notebook).

        The model was trained with an encoder where class 0 == "Low Risk"
        and class 1 == "High Risk", so probability[0][1] is the high-risk
        probability.
        """
        try:
            if joblib is None or np is None:
                return {
                    'error': 'ML dependencies are not installed. Install the backend requirements to enable predictions.',
                    'models_available': [],
                }

            # Use the trained rf_risk_model
            model = self._models.get('rf_risk_model')
            
            if not model:
                # Try to find any model as fallback
                if self._models:
                    model = list(self._models.values())[0]
                    model_name = list(self._models.keys())[0]
                    logger.warning('Using fallback model: %s', model_name)
                else:
                    error_msg = "No models loaded. Please train or add a model first."
                    return {'error': error_msg, 'models_available': list(self._models.keys())}
            
            # Build the feature vector (no scaling needed for Random Forest)
            feature_array = self._feature_vector(features)
            
            # Make prediction
            prediction = model.predict(feature_array)
            probability = model.predict_proba(feature_array)
            
            # Class 1 = "High Risk", class 0 = "Low Risk"
            if probability.shape[1] > 1:
                high_risk_prob = float(probability[0][1])
                low_risk_prob = float(probability[0][0])
            else:
                high_risk_prob = float(probability[0][0])
                low_risk_prob = None
            
            # Calculate risk score (0-100, higher = higher risk)
            risk_score = high_risk_prob * 100
            
            # Determine risk level
            if risk_score >= 70:
                risk_level = 'high'
                risk_color = 'red'
            elif risk_score >= 40:
                risk_level = 'medium'
                risk_color = 'orange'
            else:
                risk_level = 'low'
                risk_color = 'green'
            
            # Human-readable label via the label encoder if available
            label = None
            if self._label_encoder is not None:
                try:
                    label = self._label_encoder.inverse_transform([[int(prediction[0])]])[0][0]
                except Exception:
                    label = None
            
            # Generate recommendations
            recommendations = self._get_recommendations(risk_level)
            
            return {
                'prediction': label or int(prediction[0]),
                'risk_score': round(risk_score, 2),
                'risk_level': risk_level,
                'risk_color': risk_color,
                'probability': {
                    'high_risk': high_risk_prob,
                    'low_risk': low_risk_prob,
                },
                'features_used': MODEL_FEATURE_COLUMNS,
                'input_features': features,
                'recommendations': recommendations,
                'model_used': 'rf_risk_model',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.exception('Prediction error: %s', e)
            return {
                'error': str(e),
                'models_available': list(self._models.keys())
            }
    
    def build_features_from_vitals(self, user, latest_by_type):
        """
        Assemble the model's 6 required features (Heart Rate, Oxygen
        Saturation, Systolic/Diastolic BP, Derived_HR, Derived_Pulse_Pressure)
        from a patient's most recent VitalSign of each type. Used by the
        ingest pipeline so inference can run automatically on every incoming
        reading, without a person filling in a manual clinical-intake form.

        Derived_HR has no per-patient history available at inference time, so
        it falls back to the training-set-consistent default of 0.1.
        Derived_Pulse_Pressure is computed as Systolic - Diastolic.

        latest_by_type: dict of vital_type -> VitalSign (most recent of each type)
        Returns (features_dict, warnings) where warnings lists any values
        that had to fall back to a population-average default because no
        real reading/profile data was available yet.
        """
        warnings = []

        def _num(reading, keys):
            if reading is None:
                return None
            value = reading.value
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

        heart_rate = _num(latest_by_type.get('heart_rate'), ('heart_rate', 'bpm'))
        if heart_rate is None:
            heart_rate = 75.0
            warnings.append('heart_rate: no recent reading, defaulted to 75')

        oxygen_saturation = _num(latest_by_type.get('oxygen_saturation'), ('spo2', 'oxygen_saturation'))
        if oxygen_saturation is None:
            oxygen_saturation = 97.0
            warnings.append('oxygen_saturation: no recent reading, defaulted to 97')

        bp_reading = latest_by_type.get('blood_pressure')
        systolic_bp = diastolic_bp = None
        if bp_reading is not None and isinstance(bp_reading.value, dict):
            systolic_bp = _num(bp_reading, ('systolic', 'systolic_bp', 'upper'))
            diastolic_bp = _num(bp_reading, ('diastolic', 'diastolic_bp', 'lower'))
        if systolic_bp is None:
            systolic_bp = 118.0
            warnings.append('systolic_bp: no recent reading, defaulted to 118')
        if diastolic_bp is None:
            diastolic_bp = 76.0
            warnings.append('diastolic_bp: no recent reading, defaulted to 76')

        derived_pulse_pressure = round(systolic_bp - diastolic_bp, 2)
        warnings.append(
            'derived_pulse_pressure: computed as systolic - diastolic '
            f'({derived_pulse_pressure} mmHg)'
        )

        features = {
            'heart_rate': heart_rate,
            'oxygen_saturation': oxygen_saturation,
            'systolic_bp': systolic_bp,
            'diastolic_bp': diastolic_bp,
            'derived_hr': DERIVED_HR_DEFAULT,
            'derived_pulse_pressure': derived_pulse_pressure,
        }
        return features, warnings

    def _get_recommendations(self, risk_level):
        """Get health recommendations based on risk level"""
        recommendations = {
            'high': [
                "🚨 Immediate medical consultation required",
                "📋 Schedule comprehensive health checkup",
                "🏥 Consult with your primary care physician",
                "💊 Review all medications with your doctor",
                "📊 Monitor vital signs daily",
                "🏃 Start with light physical activity (under supervision)"
            ],
            'medium': [
                "⚠️ Health risk detected - take action",
                "📋 Schedule health checkup within 30 days",
                "🏥 Consider consulting with a healthcare provider",
                "📊 Monitor vital signs regularly",
                "🏃 Increase physical activity gradually"
            ],
            'low': [
                "✅ Good health status",
                "📋 Maintain regular health checkups",
                "🏃 Continue current exercise routine",
                "🥗 Maintain balanced diet",
                "😴 Get adequate sleep"
            ]
        }
        return recommendations.get(risk_level, recommendations['low'])

# Create singleton instance
prediction_service = HealthPredictionService()
