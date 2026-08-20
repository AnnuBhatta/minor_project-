from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from .models import Prediction
from .serializers import PredictionSerializer, HealthRiskPredictionSerializer
from ml_models.predictions.service import prediction_service
from ml_models.demo_service import demo_simulator
from ml_models.turbo_demo_service import turbo_demo_service
from ml_models.alert_generator import alert_generator
from ml_models.alert_engine import AlertManager
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


# ============================================================
# PREDICTION ENDPOINTS
# ============================================================

class HealthRiskPredictionView(APIView):
    """
    Predict health risk using Random Forest model
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            # Validate input
            serializer = HealthRiskPredictionSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # Make prediction
            result = prediction_service.predict_health_risk(serializer.validated_data)
            
            if 'error' in result:
                return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Save prediction
            prediction = Prediction.objects.create(
                user=request.user,
                prediction_type='health_risk',
                input_data=serializer.validated_data,
                result=result,
                risk_score=result.get('risk_score', 0),
                risk_level=result.get('risk_level', 'unknown')
            )
            
            # Create alert for high risk
            if result.get('risk_level') == 'high':
                self._create_health_alert(request.user, result)
            
            return Response({
                'prediction_id': prediction.id,
                'result': result
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Health risk prediction error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _create_health_alert(self, user, result):
        """Create health alert for high risk predictions"""
        try:
            from alerts.models import Alert
            
            Alert.objects.create(
                user=user,
                alert_type='abnormal_vital',
                severity='high',
                title='High Health Risk Detected',
                message=f"Health risk assessment shows high risk (Score: {result.get('risk_score')}%). Please consult a doctor.",
                status='pending'
            )
        except Exception as e:
            logger.error(f"Failed to create alert: {e}")


class PredictionHistoryView(generics.ListAPIView):
    """
    View prediction history for the current user
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PredictionSerializer
    
    def get_queryset(self):
        prediction_type = self.request.query_params.get('type')
        limit = int(self.request.query_params.get('limit', 50))
        queryset = Prediction.objects.filter(user=self.request.user)
        
        if prediction_type:
            queryset = queryset.filter(prediction_type=prediction_type)
        
        return queryset[:limit]


class ModelStatusView(APIView):
    """
    Check if ML models are loaded and ready
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        status_data = {
            'models_loaded': bool(prediction_service._models),
            'models': list(prediction_service._models.keys()),
            'scalers_loaded': bool(prediction_service._scalers),
            'scalers': list(prediction_service._scalers.keys()),
            'feature_config': prediction_service._feature_config,
            'alert_engine_ready': True
        }
        return Response(status_data)


# ============================================================
# ALERT ENGINE ENDPOINTS
# ============================================================

class GetAlertStatusView(APIView):
    """
    Get current alert engine status for the user
    Shows debouncing state, consecutive high risk count, etc.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            user_id = request.user.id
            engine = AlertManager.get_engine(user_id)
            
            return Response({
                'status': 'ok',
                'user_id': user_id,
                'consecutive_high_risk': engine.consecutive_high_risk_count,
                'tier2_last_fired': engine.tier2_last_fired.isoformat() if engine.tier2_last_fired else None,
                'tier3_last_fired': engine.tier3_last_fired.isoformat() if engine.tier3_last_fired else None,
                'recent_readings_count': len(engine.recent_readings),
                'tier3_cooldown_minutes': engine.tier3_cooldown_minutes,
                'tier_requirements': {
                    'tier1': 'Critical threshold breach - immediate',
                    'tier2': f'3 consecutive high-risk readings (current: {engine.consecutive_high_risk_count}/3)',
                    'tier3': f'30-min cooldown, {len(engine.recent_readings)} readings in history'
                }
            })
            
        except Exception as e:
            logger.error(f"Alert status error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResetAlertEngineView(APIView):
    """
    Reset alert engine for the user (for testing)
    Clears consecutive counts and cooldown timers
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            user_id = request.user.id
            AlertManager.clear_engine(user_id)
            
            return Response({
                'status': 'success',
                'message': f'Alert engine reset for user {user_id}',
                'user_id': user_id
            })
            
        except Exception as e:
            logger.error(f"Reset alert engine error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# DEMO SIMULATION ENDPOINTS (dataset replay)
# ============================================================

class StartDemoView(APIView):
    """
    POST /api/demo/start/ (also /api/ml/demo/start/)
    Start replaying the real training dataset (vital_signs_dataset.csv)
    through the live ingest pipeline as simulated smartwatch data. Every
    reading runs RF + LSTM inference and the three-tier alert system, so
    alerts reach the guardian dashboard via WebSocket exactly as they would
    for a real device.

    Body (all optional):
      interval_seconds : seconds between readings (default 2.0; 120 = the
                         dataset's real 2-minute cadence)
      patient_ids      : restrict replay to these dataset patient ids
      max_cycles       : stop after this many full passes (None = run until
                         stopped)
      max_readings     : stop after this many individual readings
      sample_readings  : replay a random subset of this many real dataset
                         rows (fast demo: e.g. 100 readings instead of all
                         200,258)
      patient_id       : Django user id the readings are written to
                         (defaults to the requesting user)
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            interval = float(request.data.get('interval_seconds', 2.0))
            interval = max(0.5, min(interval, 120))

            patient_ids = request.data.get('patient_ids')
            if isinstance(patient_ids, str):
                patient_ids = [int(x) for x in patient_ids.split(',') if x.strip()]

            max_cycles = request.data.get('max_cycles')
            if max_cycles is not None:
                max_cycles = int(max_cycles)

            max_readings = request.data.get('max_readings')
            if max_readings is not None:
                max_readings = int(max_readings)

            sample_readings = request.data.get('sample_readings')
            if sample_readings is not None:
                sample_readings = int(sample_readings)

            result = demo_simulator.start_dataset_replay(
                requester=request.user,
                target_patient_id=request.data.get('patient_id'),
                interval_seconds=interval,
                patient_ids=patient_ids,
                max_cycles=max_cycles,
                max_readings=max_readings,
                sample_readings=sample_readings,
            )
            return Response({
                'status': 'started',
                'message': 'Dataset replay started through the live pipeline.',
                'replay': result,
            }, status=status.HTTP_200_OK)

        except FileNotFoundError as e:
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_404_NOT_FOUND)
        except (ValueError, TypeError) as e:
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Failed to start demo replay: {e}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StopDemoView(APIView):
    """
    POST /api/demo/stop/ (also /api/ml/demo/stop/)
    Stop the dataset replay stream.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            demo_simulator.stop_dataset_replay()
            return Response({'status': 'stopped', 'message': 'Demo replay stopped.'})
        except Exception as e:
            logger.error(f"Failed to stop demo replay: {e}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DemoStatusView(APIView):
    """
    GET /api/demo/status/ (also /api/ml/demo/status/)
    Current replay status: running state, cycle, current patient, reading
    progress and target patient.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            return Response(demo_simulator.dataset_replay_status())
        except Exception as e:
            logger.error(f"Demo status error: {e}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DemoPatientsView(APIView):
    """
    GET /api/demo/patients/ (also /api/ml/demo/patients/)
    List every patient available in the training dataset with their reading
    counts and date ranges.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            patients = demo_simulator.list_dataset_patients()
            return Response({
                'total_patients': len(patients),
                'total_readings': sum(p['reading_count'] for p in patients),
                'patients': patients,
            })
        except FileNotFoundError as e:
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Demo patients error: {e}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# TURBO DEMO ENDPOINTS (fast dataset replay for presentations)
# ============================================================

class TurboStartDemoView(APIView):
    """
    POST /api/demo/turbo-start/ (also /api/ml/demo/turbo-start/)
    Start a fast demo replay: `readings` rows from the training dataset, one
    every `interval` seconds (default 100 readings at 1s = ~100 seconds).
    Every reading runs the full RF + LSTM + 3-tier alert pipeline and is
    pushed over WebSocket to the patient + guardian dashboards.

    Body (all optional):
      readings : number of readings to replay (default 100)
      interval : seconds between readings (default 1; 1/2/5 are the UI presets)
      patient_id : Django user the readings are written to (default: requester)
      patient_ids : restrict to specific dataset patient ids
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            readings = int(request.data.get('readings', 100))
            if readings < 1 or readings > 2000:
                return Response({'status': 'error', 'message': 'readings must be between 1 and 2000.'},
                                status=status.HTTP_400_BAD_REQUEST)

            interval = float(request.data.get('interval', 1.0))
            if interval < 0.1 or interval > 120:
                return Response({'status': 'error', 'message': 'interval must be between 0.1 and 120 seconds.'},
                                status=status.HTTP_400_BAD_REQUEST)

            patient_ids = request.data.get('patient_ids')
            if isinstance(patient_ids, str):
                patient_ids = [int(x) for x in patient_ids.split(',') if x.strip()]

            result = turbo_demo_service.start(
                requester=request.user,
                readings=readings,
                interval_seconds=interval,
                target_patient_id=request.data.get('patient_id'),
                patient_ids=patient_ids,
            )
            return Response({
                'status': 'started',
                'message': f'Turbo demo started: {readings} readings at {interval}s.',
                'replay': result,
            }, status=status.HTTP_200_OK)

        except FileNotFoundError as e:
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_404_NOT_FOUND)
        except (ValueError, TypeError) as e:
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Failed to start turbo demo: {e}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TurboStopDemoView(APIView):
    """POST /api/demo/turbo-stop/ -- stop the turbo demo stream."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            return Response(turbo_demo_service.stop())
        except Exception as e:
            logger.error(f"Failed to stop turbo demo: {e}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TurboDemoStatusView(APIView):
    """GET /api/demo/turbo-status/ -- current turbo demo progress."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            return Response(turbo_demo_service.status())
        except Exception as e:
            logger.error(f"Turbo demo status error: {e}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# GUARANTEED-ALERT DEMO ENDPOINTS
# Each posts a scripted vital pattern through the real ingest pipeline
# (RF + LSTM + 3-tier engine + WebSocket + email) so the target tier is
# guaranteed to fire. The response includes the alert reason.
# ============================================================

class TriggerTier1AlertView(APIView):
    """POST /api/demo/alert/tier1/ -- guaranteed Tier 1 (Emergency) alert.
    Sends one critical multi-parameter batch (HR 155 / SpO2 84 / SBP 195)
    so 3+ vitals breach at once -> Tier 1 + EmergencyEvent + live location."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            result = alert_generator.generate_emergency_scenario(
                request.user, request.data.get('patient_id'))
            return Response(result)
        except Exception as e:
            logger.error(f"Guaranteed Tier 1 demo failed: {e}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TriggerTier2AlertView(APIView):
    """POST /api/demo/alert/tier2/ -- guaranteed Tier 2 (Health Alert).
    Sends 3 consecutive RF-high readings -> RF counter hits 3 -> Tier 2."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            result = alert_generator.generate_health_alert_scenario(
                request.user, request.data.get('patient_id'))
            return Response(result)
        except Exception as e:
            logger.error(f"Guaranteed Tier 2 demo failed: {e}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TriggerTier3AlertView(APIView):
    """POST /api/demo/alert/tier3/ -- guaranteed Tier 3 (Trend Alert).
    Replays 1 simulated hour of gradual deterioration + 3 elevated readings
    so the LSTM reports early_warning and Tier 3 fires behind the Tier 2 gate."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            result = alert_generator.generate_trend_alert_scenario(
                request.user, request.data.get('patient_id'))
            return Response(result)
        except Exception as e:
            logger.error(f"Guaranteed Tier 3 demo failed: {e}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TriggerFullDemoView(APIView):
    """POST /api/demo/alert/full/ -- run Tier 1, Tier 2 and Tier 3 in order,
    each guaranteed to fire."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            result = alert_generator.generate_full_demo(
                request.user, request.data.get('patient_id'))
            return Response(result)
        except Exception as e:
            logger.error(f"Full guaranteed demo failed: {e}")
            return Response({'status': 'error', 'message': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GenerateTrainingDataView(APIView):
    """
    Generate training data for ML models
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            # Check if user is admin or has permission
            if not request.user.is_staff:
                return Response({
                    'error': 'Only admin users can generate training data'
                }, status=status.HTTP_403_FORBIDDEN)
            
            from ml_models.data_generator import HealthDataGenerator
            
            generator = HealthDataGenerator()
            
            # Generate datasets
            normal_data = generator.generate_normal_data(hours=72, interval_minutes=5)
            normal_path = generator.save_dataset(normal_data, 'normal_health_data.csv')
            
            anomaly_data = generator.generate_anomaly_data(hours=72, interval_minutes=5, anomaly_rate=0.15)
            anomaly_path = generator.save_dataset(anomaly_data, 'anomaly_health_data.csv')
            
            demo_data = generator.generate_demo_data(seconds=30, interval_seconds=2)
            demo_path = generator.save_dataset(demo_data, 'demo_health_data.csv')
            
            return Response({
                'status': 'success',
                'message': 'Training data generated successfully',
                'datasets': {
                    'normal_data': str(normal_path),
                    'anomaly_data': str(anomaly_path),
                    'demo_data': str(demo_path)
                },
                'records': {
                    'normal': len(normal_data),
                    'anomaly': len(anomaly_data),
                    'demo': len(demo_data)
                },
                'instructions': 'Now run: python ml_models/train_models.py'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Data generation error: {e}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TrainModelsView(APIView):
    """
    Train ML models using generated data
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            # Check if user is admin or has permission
            if not request.user.is_staff:
                return Response({
                    'error': 'Only admin users can train models'
                }, status=status.HTTP_403_FORBIDDEN)
            
            from ml_models.train_models import HealthModelTrainer
            
            trainer = HealthModelTrainer()
            
            # Check if data exists
            if not (trainer.data_dir / 'anomaly_health_data.csv').exists():
                return Response({
                    'error': 'Training data not found',
                    'instructions': 'First generate data: POST /api/ml/demo/generate-data/'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Train models
            rf_model = trainer.train_random_forest()
            lstm_model = trainer.train_lstm()
            
            # Reload the demo simulator
            global demo_simulator
            from ml_models.demo_service import demo_simulator as new_simulator
            demo_simulator = new_simulator
            
            return Response({
                'status': 'success',
                'message': 'Models trained successfully',
                'models': {
                    'random_forest': 'trained' if rf_model else 'failed',
                    'lstm': 'trained' if lstm_model else 'failed'
                },
                'model_paths': {
                    'random_forest': str(trainer.models_dir / 'random_forest_health_model.joblib'),
                    'lstm': str(trainer.models_dir / 'lstm_health_model.h5'),
                    'scaler': str(trainer.scalers_dir / 'health_scaler.joblib')
                },
                'instructions': 'Models are now ready for demo with three-tier alert system!'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Model training error: {e}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetDemoHistoryView(APIView):
    """
    Get history of demo alerts and predictions
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            from alerts.models import Alert
            
            # Get recent alerts for this user
            alerts = Alert.objects.filter(
                user=request.user,
                alert_type='abnormal_vital'
            ).order_by('-created_at')[:20]
            
            alerts_data = []
            for alert in alerts:
                # Determine tier based on alert data
                tier = 2  # Default
                if 'Emergency' in alert.title or 'EMERGENCY' in alert.message:
                    tier = 1
                elif 'Trend' in alert.title or 'deterioration' in alert.message.lower():
                    tier = 3
                
                alerts_data.append({
                    'id': alert.id,
                    'title': alert.title,
                    'message': alert.message,
                    'severity': alert.severity,
                    'status': alert.status,
                    'tier': tier,
                    'created_at': alert.created_at.isoformat()
                })
            
            return Response({
                'total_alerts': len(alerts_data),
                'alerts': alerts_data,
                'has_data': len(alerts_data) > 0,
                'alert_tiers_explained': {
                    'tier1': '🚨 Emergency - Critical threshold breach (immediate)',
                    'tier2': '⚠️ Health Alert - 3 consecutive high-risk readings',
                    'tier3': '📉 Trend Alert - Sustained deterioration over last hour'
                }
            })
            
        except Exception as e:
            logger.error(f"Demo history error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProcessSingleReadingView(APIView):
    """
    Process a single reading through the three-tier alert system
    Useful for manual testing and integration with real devices
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            user_id = request.user.id
            data = request.data.get('data', {})
            
            if not data:
                return Response({
                    'error': 'No data provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get RF prediction
            rf_prediction = demo_simulator.predict_anomaly(data) if demo_simulator.rf_model else None
            
            # Process through alert engine
            engine = AlertManager.get_engine(user_id)
            alerts = engine.process_reading(data, rf_prediction)
            
            # Create alerts in database if any
            created_alerts = []
            for alert_data in alerts:
                if alert_data.get('triggered'):
                    from alerts.models import Alert
                    
                    tier = alert_data.get('tier', 2)
                    severity = alert_data.get('severity', 'high')
                    
                    # Determine tier-specific title
                    if tier == 1:
                        title = '🚨 EMERGENCY: Critical Vital Signs'
                        severity = 'critical'
                    elif tier == 2:
                        title = '⚠️ Health Alert: Elevated Risk Detected'
                        severity = 'high'
                    else:
                        title = '📉 Trend Alert: Gradual Deterioration'
                        severity = 'medium'
                    
                    alert = Alert.objects.create(
                        user=request.user,
                        alert_type='abnormal_vital',
                        severity=severity,
                        title=title,
                        message=alert_data.get('message', 'Health anomaly detected'),
                        status='pending',
                        location={'lat': 28.6139, 'lng': 77.2090}
                    )
                    
                    created_alerts.append({
                        'id': alert.id,
                        'tier': tier,
                        'message': alert.message
                    })
            
            return Response({
                'status': 'success',
                'user_id': user_id,
                'rf_prediction': rf_prediction,
                'alerts_triggered': alerts,
                'alerts_created': created_alerts,
                'debounce_status': {
                    'consecutive_high_risk': engine.consecutive_high_risk_count,
                    'tier2_last_fired': engine.tier2_last_fired.isoformat() if engine.tier2_last_fired else None,
                    'tier3_last_fired': engine.tier3_last_fired.isoformat() if engine.tier3_last_fired else None,
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Process reading error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)