"""
Email alert delivery for the health-monitoring app.

Uses Gmail SMTP (django.core.mail.backends.smtp.EmailBackend, port 587/TLS)
configured in config/settings.py. Emails are sent on a background thread so a
slow SMTP round-trip never blocks the ingest/alert response.

Usage (from anywhere in the alert pipeline):
    from alerts.services import send_alert_email

    send_alert_email(
        patient=patient,
        alert_type=alert.alert_type,
        severity=alert.severity,
        title=alert.title,
        message=alert.message,
        location=alert.location,
        timestamp=alert.created_at,
    )

The function is best-effort: any exception is logged and swallowed so a broken
SMTP setup never takes the app down.
"""
import logging
from threading import Thread

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger('alerts')


def get_guardian_emails(patient):
    """All recipient email addresses for a patient: approved guardians plus
    the patient's own direct emergency contact email (deduplicated)."""
    emails = []

    for guardian in patient.guardians.all():
        if guardian.email and guardian.email not in emails:
            emails.append(guardian.email)

    if patient.emergency_contact_email and patient.emergency_contact_email not in emails:
        emails.append(patient.emergency_contact_email)

    return emails


def get_latest_vitals(patient):
    """Latest reading of each vital type as a flat dict, keyed by the model
    feature names the alert templates display."""
    from vitals.models import VitalSign

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

    latest = {}
    for reading in VitalSign.objects.filter(user=patient).order_by('-timestamp')[:100]:
        latest.setdefault(reading.vital_type, reading)

    vitals = {}

    hr = latest.get('heart_rate')
    if hr is not None:
        value = _number(hr.value, ('heart_rate', 'bpm'))
        if value is not None:
            vitals['Heart Rate'] = {'value': value, 'unit': 'bpm'}

    spo2 = latest.get('oxygen_saturation')
    if spo2 is not None:
        value = _number(spo2.value, ('spo2', 'oxygen_saturation'))
        if value is not None:
            vitals['Oxygen Saturation'] = {'value': value, 'unit': '%'}

    bp = latest.get('blood_pressure')
    if bp is not None and isinstance(bp.value, dict):
        systolic = _number(bp.value, ('systolic', 'systolic_bp', 'upper'))
        diastolic = _number(bp.value, ('diastolic', 'diastolic_bp', 'lower'))
        if systolic is not None and diastolic is not None:
            vitals['Blood Pressure'] = {
                'value': f"{systolic:.0f}/{diastolic:.0f}",
                'unit': 'mmHg',
            }

    return vitals


def send_alert_email(
    patient,
    alert_type,
    severity,
    title,
    message,
    timestamp=None,
    location=None,
    vital_signs=None,
    recipient_emails=None,
    emergency_url=None,
    async_send=True,
):
    """Send a styled HTML alert email to the patient's guardians.

    Args:
        patient: the affected User (patient).
        alert_type: e.g. 'emergency', 'abnormal_vital'.
        severity: 'low' / 'medium' / 'high' / 'critical'.
        title: short alert title.
        message: human-readable alert description.
        timestamp: datetime of the alert (defaults to now).
        location: dict with 'lat'/'lng' (optional).
        vital_signs: flat dict of the latest vitals (optional; auto-fetched).
        recipient_emails: explicit list of recipients (defaults to guardians).
        emergency_url: absolute link for the CTA button (auto-built when None).
        async_send: when True, send on a background thread.

    Returns True if the send was dispatched successfully, False otherwise.
    """
    try:
        if vital_signs is None:
            vital_signs = get_latest_vitals(patient)

        recipients = recipient_emails or get_guardian_emails(patient)
        recipients = [email for email in recipients if email]

        if not recipients:
            logger.warning("No email recipients for alert '%s' (patient %s)", title, patient.id)
            return False

        if emergency_url is None:
            base = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')
            emergency_url = f"{base}/emergency"

        timestamp = timestamp or timezone.now()

        location = location or {}
        lat = location.get('lat', location.get('latitude'))
        lng = location.get('lng', location.get('longitude'))
        location = {'lat': lat, 'lng': lng}

        context = {
            'patient_name': patient.get_full_name() or patient.email,
            'patient_email': patient.email,
            'patient_phone': patient.phone or '',
            'alert_type': alert_type,
            'alert_type_label': str(alert_type).replace('_', ' ').title(),
            'severity': severity,
            'severity_label': str(severity).title(),
            'title': title,
            'message': message,
            'timestamp': timestamp,
            'location': location,
            'vital_signs': vital_signs,
            'emergency_url': emergency_url,
            'frontend_url': base,
        }

        html_body = render_to_string('alerts/alert_email.html', context)
        text_body = _plain_text_body(context)

        email = EmailMultiAlternatives(
            subject=f"[{context['severity_label']}] {title} - {context['patient_name']}",
            body=text_body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_HOST_USER),
            to=recipients,
            reply_to=[patient.email] if patient.email else None,
        )
        email.attach_alternative(html_body, 'text/html')

        if async_send:
            thread = Thread(target=_send_safely, args=(email, context), daemon=True)
            thread.start()
            logger.info("Dispatched alert email to %s on background thread", recipients)
            return True

        _send_safely(email, context)
        return True

    except Exception:
        logger.exception("Failed to prepare alert email for patient %s", patient.id)
        return False


def _send_safely(email, context):
    """Run the actual SMTP send, logging success/failure. Never raises."""
    try:
        email.send(fail_silently=False)
        logger.info("Alert email sent to %s (subject: %s)", email.to, email.subject)
    except Exception:
        logger.exception(
            "Failed to send alert email to %s (subject: %s)",
            email.to,
            email.subject,
        )


def _plain_text_body(context):
    """Fallback plain-text body for email clients that strip HTML."""
    lines = [
        f"{context['title']}",
        "",
        f"Patient: {context['patient_name']} ({context['patient_email']})",
        f"Alert Type: {context['alert_type_label']}",
        f"Severity: {context['severity_label']}",
        f"Time: {context['timestamp']}",
        "",
        context['message'],
        "",
    ]
    if context['vital_signs']:
        lines.append("Latest vitals:")
        for name, info in context['vital_signs'].items():
            lines.append(f"  - {name}: {info['value']} {info.get('unit', '')}".rstrip())
        lines.append("")
    if context['location']:
        lat = context['location'].get('lat', context['location'].get('latitude', 'N/A'))
        lng = context['location'].get('lng', context['location'].get('longitude', 'N/A'))
        lines.append(f"Location: {lat}, {lng}")
        lines.append(f"Open in Google Maps: https://www.google.com/maps?q={lat},{lng}")
        lines.append("")
    lines.append(f"View details: {context['emergency_url']}")
    return "\n".join(lines)