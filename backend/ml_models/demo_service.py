import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
import json
import time
from datetime import datetime
import random
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .alert_engine import alert_manager
from .data_replay import data_replay_service
import logging

logger = logging.getLogger(__name__)

class DemoHealthSimulator:
    """Simulate real-time health data for demo purposes"""
    
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent
        self.models_dir = self.base_dir / 'models'
        self.scalers_dir = self.base_dir / 'scalers'
        
        # Load models
        self.rf_model = None
        self.scaler = None
        self.feature_columns = []
        
        self.load_models()
        
        print("✅ Demo simulator initialized")
    
    def load_models(self):
        """Load ML models"""
        try:
            rf_path = self.models_dir / 'rf_risk_model.joblib'
            
            if rf_path.exists():
                self.rf_model = joblib.load(rf_path)
                self.scaler = None  # Random Forest needs no feature scaling
                self.feature_columns = list(getattr(self.rf_model, 'feature_names_in_', []))
                
                print(f"✅ Loaded Random Forest model with {len(self.feature_columns)} features")
            else:
                print("⚠️ Models not found. Train models first.")
                
        except Exception as e:
            logger.error(f"Error loading models: {e}")
    
    def generate_real_time_data(self):
        """Generate simulated real-time health data using the six model
        features (Heart Rate, Oxygen Saturation, Systolic/Diastolic BP,
        Derived_HR, Derived_Pulse_Pressure)."""
        systolic = random.randint(90, 140)
        diastolic = random.randint(60, 90)
        data = {
            'heart_rate': random.randint(60, 100),
            'blood_pressure_systolic': systolic,
            'blood_pressure_diastolic': diastolic,
            'oxygen_saturation': random.randint(95, 100),
            'derived_hr': round(random.uniform(0.05, 0.15), 3),
            'derived_pulse_pressure': systolic - diastolic,
        }
        return data
    
    def generate_anomaly_data(self):
        """Generate data with anomalies (for demo) using the six model
        features (Heart Rate, Oxygen Saturation, Systolic/Diastolic BP,
        Derived_HR, Derived_Pulse_Pressure)."""
        anomaly_types = [
            {'heart_rate': (150, 180)},  # Tachycardia
            {'heart_rate': (30, 45)},  # Bradycardia
            {'blood_pressure_systolic': (180, 200), 'blood_pressure_diastolic': (95, 120)},  # Hypertension
            {'blood_pressure_systolic': (70, 85), 'blood_pressure_diastolic': (40, 50)},  # Hypotension
            {'oxygen_saturation': (80, 90)},  # Hypoxia
        ]
        
        chosen = random.choice(anomaly_types)
        
        data = self.generate_real_time_data()
        
        # Override with anomaly
        for key, value in chosen.items():
            if key in data:
                if isinstance(value, tuple):
                    data[key] = random.randint(*value)
                else:
                    data[key] = value
        
        # Keep the derived feature consistent with the anomaly's pressures
        data['derived_pulse_pressure'] = data['blood_pressure_systolic'] - data['blood_pressure_diastolic']
        
        return data
    
    def generate_trend_data(self):
        """Generate data that shows gradual deterioration (for LSTM)"""
        data = self.generate_real_time_data()
        
        # Gradually increase heart rate and blood pressure
        hr = data['heart_rate']
        bp = data['blood_pressure_systolic']
        
        # Add trend (slightly elevated)
        hr_increase = random.randint(10, 20)
        bp_increase = random.randint(15, 25)
        
        data['heart_rate'] = min(hr + hr_increase, 150)
        data['blood_pressure_systolic'] = min(bp + bp_increase, 180)
        data['derived_pulse_pressure'] = data['blood_pressure_systolic'] - data['blood_pressure_diastolic']
        
        return data
    
    def predict_anomaly(self, data):
        """Predict if data contains anomaly using RF"""
        if not self.rf_model:
            return {
                'is_anomaly': False,
                'confidence': 0,
                'probability': {'low_risk': 1.0, 'high_risk': 0.0}
            }
        
        try:
            # Build the 6 model features from the simulator's data dict
            def _num(data, *keys):
                for key in keys:
                    value = data.get(key)
                    if value is not None:
                        try:
                            return float(value)
                        except (TypeError, ValueError):
                            continue
                return 0.0

            heart_rate = _num(data, 'heart_rate', 'Heart Rate')
            oxygen_saturation = _num(data, 'oxygen_saturation', 'Oxygen Saturation')
            systolic_bp = _num(data, 'blood_pressure_systolic', 'Systolic Blood Pressure')
            diastolic_bp = _num(data, 'blood_pressure_diastolic', 'Diastolic Blood Pressure')
            derived_hr = _num(data, 'derived_hr', 'Derived_HR') or 0.1
            pulse_pressure = _num(data, 'derived_pulse_pressure', 'Derived_Pulse_Pressure')
            if not pulse_pressure and systolic_bp and diastolic_bp:
                pulse_pressure = round(systolic_bp - diastolic_bp, 2)

            row = {
                'Heart Rate': heart_rate,
                'Oxygen Saturation': oxygen_saturation,
                'Systolic Blood Pressure': systolic_bp,
                'Diastolic Blood Pressure': diastolic_bp,
                'Derived_HR': derived_hr,
                'Derived_Pulse_Pressure': pulse_pressure,
            }
            features = np.array([[row[col] for col in self.feature_columns]]).reshape(1, -1)
            
            # Predict (class 1 = "High Risk", class 0 = "Low Risk")
            prediction = self.rf_model.predict(features)
            probability = self.rf_model.predict_proba(features)
            
            high_risk = float(probability[0][1]) if probability.shape[1] > 1 else float(probability[0][0])
            low_risk = float(probability[0][0]) if probability.shape[1] > 1 else (1.0 - high_risk)
            
            return {
                'is_anomaly': bool(prediction[0] == 1),
                'confidence': float(high_risk),
                'probability': {
                    'low_risk': low_risk,
                    'high_risk': high_risk
                }
            }
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {
                'is_anomaly': False,
                'confidence': 0,
                'probability': {'low_risk': 1.0, 'high_risk': 0.0}
            }
    
    def run_demo(self, user_id, duration_seconds=30, interval_seconds=2):
        """
        Run demo simulation with three-tier alert system
        """
        print(f"\n🚀 Starting health demo simulation for {duration_seconds} seconds...")
        print(f"📊 Data will be sent every {interval_seconds} seconds")
        print(f"🔴 Tier 1: Emergency (immediate)")
        print(f"🟡 Tier 2: Health Alert (3 consecutive readings)")
        print(f"🔵 Tier 3: Trend Alert (30-min cooldown)")
        print("-" * 60)
        
        channel_layer = get_channel_layer()
        start_time = datetime.now()
        
        # Reset the alert engine for this user
        from .alert_engine import AlertManager
        AlertManager.clear_engine(user_id)
        alert_engine = AlertManager.get_engine(user_id)
        
        reading_count = 0
        phase = 0  # 0=normal, 1=anomaly, 2=trend
        
        for i in range(int(duration_seconds / interval_seconds)):
            # Cycle through different phases for demo
            if i >= 0 and i < 5:
                # Normal phase
                data = self.generate_real_time_data()
                phase = "NORMAL"
            elif i >= 5 and i < 9:
                # Anomaly phase (sustained - for Tier 2)
                data = self.generate_anomaly_data()
                phase = "ANOMALY"
            elif i >= 10 and i < 14:
                # Trend phase (gradual deterioration)
                data = self.generate_trend_data()
                phase = "TREND"
            elif i >= 15 and i < 19:
                # Anomaly again
                data = self.generate_anomaly_data()
                phase = "ANOMALY"
            else:
                # Back to normal
                data = self.generate_real_time_data()
                phase = "NORMAL"
            
            # Predict with RF
            rf_prediction = self.predict_anomaly(data)
            
            # Process through alert engine (Tier 1, 2, 3)
            alerts = alert_engine.process_reading(data, rf_prediction)
            
            # Prepare message
            message = {
                'type': 'health_data_update',
                'user_id': user_id,
                'timestamp': datetime.now().isoformat(),
                'reading_number': i + 1,
                'phase': phase,
                'data': data,
                'rf_prediction': rf_prediction,
                'alerts': alerts,
                'debounce_status': {
                    'consecutive_high_risk': alert_engine.consecutive_high_risk_count,
                    'tier2_last_fired': alert_engine.tier2_last_fired.isoformat() if alert_engine.tier2_last_fired else None,
                    'tier3_last_fired': alert_engine.tier3_last_fired.isoformat() if alert_engine.tier3_last_fired else None,
                }
            }
            
            # Send via WebSocket
            async_to_sync(channel_layer.group_send)(
                f"user_{user_id}_health",
                {
                    'type': 'health_update',
                    'message': message
                }
            )
            
            # Print status
            status_icons = {
                'NORMAL': '🟢',
                'ANOMALY': '🟡',
                'TREND': '🔵'
            }
            
            alert_icon = "✅"
            if alerts:
                tier = alerts[0].get('tier', 0)
                if tier == 1:
                    alert_icon = "🔴🚨"
                elif tier == 2:
                    alert_icon = "🟡⚠️"
                elif tier == 3:
                    alert_icon = "🔵📉"
            
            print(f"[{i+1:2d}] {status_icons.get(phase, '⚪')} {phase:7s} | "
                  f"HR: {data['heart_rate']:3d} | "
                  f"BP: {data['blood_pressure_systolic']:3d}/{data['blood_pressure_diastolic']:2d} | "
                  f"SpO2: {data['oxygen_saturation']:3d} | "
                  f"RF: {'🔴' if rf_prediction['is_anomaly'] else '🟢'} | "
                  f"Alert: {alert_icon}")
            
            # Show debounce status if in anomaly phase
            if phase == "ANOMALY" and rf_prediction['is_anomaly']:
                print(f"    └─ Consecutive high risk: {alert_engine.consecutive_high_risk_count}/3")
            
            reading_count += 1
            time.sleep(interval_seconds)
        
        print("\n" + "=" * 60)
        print(f"📊 Demo Summary:")
        print(f"   Total readings: {reading_count}")
        print(f"   Tier 1 (Emergency) alerts: {sum(1 for a in alerts if a.get('tier') == 1)}")
        print(f"   Tier 2 (Health Alert) alerts: {sum(1 for a in alerts if a.get('tier') == 2)}")
        print(f"   Tier 3 (Trend Alert) alerts: {sum(1 for a in alerts if a.get('tier') == 3)}")
        print("=" * 60)
        print("✅ Demo simulation complete!")
    
    def create_alert(self, user_id, data, prediction):
        """Create emergency alert"""
        from alerts.models import Alert
        
        alert_message = f"Anomaly detected in health data:\n"
        alert_message += f"Heart Rate: {data['heart_rate']} bpm\n"
        alert_message += f"Blood Pressure: {data['blood_pressure_systolic']}/{data['blood_pressure_diastolic']} mmHg\n"
        alert_message += f"Oxygen Saturation: {data['oxygen_saturation']}%\n"
        alert_message += f"Derived_HR: {data['derived_hr']}\n"
        alert_message += f"Derived_Pulse_Pressure: {data['derived_pulse_pressure']} mmHg"
        
        alert = Alert.objects.create(
            user_id=user_id,
            alert_type='abnormal_vital',
            severity='high',
            title='🚨 Health Anomaly Detected!',
            message=alert_message,
            status='pending',
            location={'lat': 28.6139, 'lng': 77.2090}  # Demo location
        )
        
        print(f"\n🚨 ALERT CREATED! ID: {alert.id}")
        print(f"   {alert.title}")
        print(f"   {alert.message[:100]}...")
        
        # Send emergency notification
        from emergency.services import send_emergency_alert
        send_emergency_alert(alert)
        
        return alert

    # ------------------------------------------------------------------ #
    # Dataset replay (delegates to DataReplayService)
    # ------------------------------------------------------------------ #
    def start_dataset_replay(self, requester, target_patient_id=None,
                             interval_seconds=2.0, patient_ids=None,
                             max_cycles=None, max_readings=None,
                             sample_readings=None):
        """Replay the real training dataset through the live ingest pipeline.

        `sample_readings` replays a random subset of that many real dataset
        rows so the demo is fast (e.g. 100 readings) instead of walking all
        200,258 rows."""
        return data_replay_service.start(
            requester,
            target_patient_id=target_patient_id,
            interval_seconds=interval_seconds,
            patient_ids=patient_ids,
            max_cycles=max_cycles,
            max_readings=max_readings,
            sample_readings=sample_readings,
        )

    def stop_dataset_replay(self):
        return data_replay_service.stop()

    def dataset_replay_status(self):
        return data_replay_service.get_status()

    def list_dataset_patients(self):
        return data_replay_service.list_patients()


# Singleton instance
demo_simulator = DemoHealthSimulator()