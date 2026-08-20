"""
Delivery layer for the three-tier alert engine.

Turns an engine decision into the channels a guardian actually experiences:
  1. An `Alert` row in the database (polled by /api/alerts/).
  2. A live WebSocket push to the patient and its guardians' `/ws/alerts/`
     sessions.
  3. For Tier 1: a full `EmergencyEvent` + FCM push (with live location),
     reusing the manual-SOS delivery path so automatic hard-threshold
     breaches reach guardians exactly like a panic button press.
  4. For Tier 2/3: an FCM push to guardians with the patient's latest
     location in the data payload.

FCM delivery is best-effort: guardians without a saved `fcm_token` are
skipped, and any Firebase error is logged without breaking the ingest
pipeline.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from alerts.models import Alert
from emergency.models import EmergencyEvent
from location.models import UserLocation

logger = logging.getLogger(__name__)

TIER_META = {
    1: {'alert_type': 'emergency', 'severity': 'critical', 'title': '🚨 EMERGENCY: Critical Vital Signs'},
    2: {'alert_type': 'abnormal_vital', 'severity': 'high', 'title': '⚠️ Health Alert: Elevated Risk Detected'},
    3: {'alert_type': 'abnormal_vital', 'severity': 'medium', 'title': '📉 Trend Alert: Gradual Deterioration'},
}


def _latest_location(patient):
    """Most recent UserLocation as {lat, lng}, or None if never reported."""
    loc = UserLocation.objects.filter(user=patient).first()
    if loc is None or loc.latitude is None or loc.longitude is None:
        return None
    return {'lat': float(loc.latitude), 'lng': float(loc.longitude)}


def _guardians(patient):
    return list(patient.guardians.all())


def broadcast_alert(patient, payload):
    """Push a new_alert message to the patient and every guardian."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"user_{patient.id}_alerts",
            {'type': 'new_alert', 'alert': payload},
        )
        for guardian in _guardians(patient):
            async_to_sync(channel_layer.group_send)(
                f"guardian_{guardian.id}_alerts",
                {'type': 'new_alert', 'alert': payload},
            )
    except Exception:
        logger.exception('Failed to broadcast alert for patient %s', patient.id)


def broadcast_emergency_location(patient, location):
    """Push the live location to guardian emergency groups (location app flow)."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        for guardian in _guardians(patient):
            async_to_sync(channel_layer.group_send)(
                f"guardian_{guardian.id}_emergency",
                {
                    'type': 'emergency_location',
                    'location': {
                        'user_id': patient.id,
                        'user_name': patient.get_full_name(),
                        'patient_phone': patient.phone or '',
                        'latitude': location['lat'],
                        'longitude': location['lng'],
                        'timestamp': None,
                    },
                },
            )
    except Exception:
        logger.exception('Failed to broadcast emergency location for patient %s', patient.id)


def notify_guardians_fcm(patient, title, body, data):
    """Best-effort FCM push to all emergency recipients (guardians included)."""
    try:
        from emergency.services import get_emergency_recipients, send_fcm_notification
        for recipient in get_emergency_recipients(patient):
            if not recipient.fcm_token:
                continue
            try:
                send_fcm_notification(
                    device_token=recipient.fcm_token,
                    title=title,
                    body=body,
                    data=data,
                )
            except Exception:
                logger.exception('FCM push failed for %s', recipient.email)
    except Exception:
        logger.exception('FCM push to guardians failed for patient %s', patient.id)


def _alert_payload(patient, alert, meta, location):
    return {
        'id': alert.id,
        'tier': meta['tier'],
        'alert_type': alert.alert_type,
        'severity': alert.severity,
        'title': alert.title,
        'message': alert.message,
        'status': alert.status,
        'created_at': alert.created_at.isoformat(),
        'location': location,
        'user_id': patient.id,
        'user_name': patient.get_full_name(),
    }


def deliver_alert(patient, engine_alert):
    """
    Persist and push a triggered engine alert (dict with 'tier'/'message').
    Returns the created Alert id, or None.
    """
    tier = engine_alert.get('tier')
    meta = TIER_META.get(tier)
    if meta is None:
        logger.warning('Unknown alert tier %s for patient %s', tier, patient.id)
        return None

    location = _latest_location(patient)

    alert = Alert.objects.create(
        user=patient,
        alert_type=meta['alert_type'],
        severity=meta['severity'],
        title=meta['title'],
        message=engine_alert.get('message', 'Health anomaly detected'),
        status='pending',
        location=location,
    )

    payload = _alert_payload(patient, alert, {**meta, 'tier': tier}, location)
    broadcast_alert(patient, payload)

    # Backup email channel (async + best-effort; never blocks the pipeline).
    try:
        from alerts.services import send_alert_email
        send_alert_email(
            patient=patient,
            alert_type=alert.alert_type,
            severity=alert.severity,
            title=alert.title,
            message=alert.message,
            timestamp=alert.created_at,
            location=location,
        )
    except Exception:
        logger.exception('Alert email delivery failed for patient %s', patient.id)

    fcm_data = {
        'type': 'tier_alert',
        'tier': str(tier),
        'alert_id': str(alert.id),
        'patient_id': str(patient.id),
        'patient_name': patient.get_full_name(),
        'timestamp': alert.created_at.isoformat(),
    }
    if location:
        fcm_data.update({'lat': str(location['lat']), 'lng': str(location['lng'])})

    if tier == 1:
        try:
            event = EmergencyEvent.objects.create(
                user=patient,
                alert=alert,
                location=location or {'lat': None, 'lng': None},
                severity='critical',
                status='active',
                is_manual=False,
                description=alert.message,
            )
            if location:
                broadcast_emergency_location(patient, location)
            try:
                from emergency.services import send_emergency_alert
                send_emergency_alert(event)
            except Exception:
                logger.exception('EmergencyEvent FCM delivery failed for event %s', event.id)
            logger.info('Tier 1 emergency delivered for patient %s (event %s)', patient.id, event.id)
        except Exception:
            logger.exception('Failed to create EmergencyEvent for patient %s', patient.id)
    else:
        notify_guardians_fcm(patient, alert.title, alert.message, fcm_data)
        logger.info('Tier %s alert delivered for patient %s (alert %s)', tier, patient.id, alert.id)

    return alert.id
