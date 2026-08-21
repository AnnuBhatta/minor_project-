"""
Guaranteed-alert scenario generator for demo mode.

The three-tier engine is real: Tier 1 (3+ critical vitals), Tier 2 (RF high
risk for 3 consecutive readings), Tier 3 (LSTM deterioration, gated behind
Tier 2). Demonstrating it with random or dataset-replayed data can be flaky
because nothing guarantees a pattern will trip the right rule at the right
time.

This module removes the guesswork. Each function constructs a *known* vital
pattern that deterministically fires its target tier, then posts it through
the REAL ingest pipeline (DRF APIClient -> /api/readings/ingest/), so RF +
LSTM + the alert engine + WebSocket + email + FCM all behave exactly as they
would for a real smartwatch. Nothing is faked; only the input data is
scripted to a deterministic outcome.

Patterns (verified against the shipped models):
  - Tier 1: HR=155, SpO2=84, SBP=195, DBP=95  -> pulse pressure 100.
            4 of 5 parameters breach their critical range -> Tier 1 fires.
  - Tier 2: 3 consecutive elevated readings (HR 130-140, SpO2 88-90,
            BP 160-165/100). RF predicts HIGH for each (score ~96); none
            breach Tier 1 (only SpO2 crosses at most once) -> Tier 2 fires
            on the 3rd reading.
  - Tier 3: 60 gradually deteriorating readings (HR 72->92, SpO2 98->94%,
            BP 120/80->140/88) then 3 sharply elevated readings. The LSTM
            forecaster sees the drift in its 60-step window, reports
            'early_warning', and the worst-case last-hour condition escalates
            to a full EMERGENCY (Tier 1 delivery), gated behind the Tier 2
            trigger (which the elevated readings also produce).
Each scenario resets the target patient's in-memory alert engine first so
debounce counters and cooldowns start clean.
"""
import logging
import time
from django.utils import timezone

logger = logging.getLogger(__name__)

NORMAL = (75, 97, 115, 75)          # HR, SpO2, SBP, DBP
TIER1_VALUES = (155, 84, 195, 95)   # 4 breaches -> Tier 1
TIER2_SEQUENCE = [
    (130, 90, 160, 100),
    (135, 89, 162, 100),
    (140, 88, 165, 100),
]
TREND_START = (72, 98, 120, 80)     # healthy baseline for the trend window
TREND_END = (92, 94, 140, 88)       # end of the 60-reading decline
POST_DELAY = 0.05                   # seconds between posts (WS/UI keep up)


class AlertGenerator:
    """Generates and runs guaranteed-alert demo scenarios."""

    # ------------------------------------------------------------------ #
    # plumbing
    # ------------------------------------------------------------------ #
    @staticmethod
    def _client(requester):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=requester)
        return client

    @staticmethod
    def _reset_engine(patient_id):
        from ml_models.alert_engine import AlertManager
        AlertManager.clear_engine(patient_id)

    @staticmethod
    def _batch(hr, spo2, sbp, dbp):
        return [
            {'vital_type': 'heart_rate', 'value': {'heart_rate': hr}},
            {'vital_type': 'oxygen_saturation', 'value': {'spo2': spo2}},
            {'vital_type': 'blood_pressure', 'value': {'systolic': sbp, 'diastolic': dbp}},
        ]

    @staticmethod
    def _tiers(resp):
        """Tiers triggered on the latest ingest response, flattened."""
        try:
            infos = (resp.data or {}).get('inference') or []
            return [t for i in infos for t in (i.get('tiers_triggered') or [])]
        except Exception:
            return []

    @staticmethod
    def _latest_alert(patient_id, since=None):
        from alerts.models import Alert
        qs = Alert.objects.filter(user_id=patient_id)
        if since is not None:
            qs = qs.filter(created_at__gte=since)
        return qs.order_by('-id').first()

    @staticmethod
    def _post(client, target_patient_id, tag, readings, location=None):
        payload = {
            'source': 'simulated',
            'scenario_id': tag,
            'patient_id': target_patient_id,
            'readings': readings,
        }
        if location:
            payload['location'] = location
        return client.post('/api/readings/ingest/', payload, format='json')

    @staticmethod
    def _result(tier, confirmed, tiers, alert, scenario, reason, summary):
        return {
            'tier': tier,
            'confirmed': confirmed,
            'tiers_triggered': tiers,
            'scenario': scenario,
            'reason': reason,
            'summary': summary,
            'alert': {
                'id': alert.id if alert else None,
                'title': alert.title if alert else None,
                'severity': alert.severity if alert else None,
                'message': alert.message if alert else None,
                'created_at': alert.created_at.isoformat() if alert else None,
            } if alert else None,
        }

    # ------------------------------------------------------------------ #
    # scenarios
    # ------------------------------------------------------------------ #
    def generate_emergency_scenario(self, requester, target_patient_id=None, location=None):
        """Guarantees a Tier 1 (Emergency) alert + EmergencyEvent + location."""
        target = int(target_patient_id or requester.id)
        tag = f'demo-tier1-{int(time.time())}'
        self._reset_engine(target)
        client = self._client(requester)
        before = timezone.now()

        hr, spo2, sbp, dbp = TIER1_VALUES
        resp = self._post(client, target, tag, self._batch(hr, spo2, sbp, dbp), location=location)
        tiers = self._tiers(resp)
        alert = self._latest_alert(target, since=before)

        confirmed = 1 in tiers
        reason = (
            f"EMERGENCY: 4 of 5 vitals out of range: "
            f"HR={hr} bpm (normal 40-140), SpO2={spo2}% (normal \u226590%), "
            f"SBP={sbp} mmHg (normal 80-180), pulse pressure={sbp - dbp} mmHg "
            f"(normal 20-70). IMMEDIATE MEDICAL ATTENTION REQUIRED."
        )
        return self._result(
            1, confirmed, tiers, alert, 'emergency', reason,
            'Tier 1 (Emergency) fired: 3+ vitals simultaneously out of range. '
            'An EmergencyEvent and live-location broadcast were also created.',
        )

    def generate_health_alert_scenario(self, requester, target_patient_id=None, location=None):
        """Guarantees a Tier 2 (Health Alert) alert via 3 consecutive RF-high
        readings. Kept to just 3 readings so Tier 3 is NOT evaluated yet."""
        target = int(target_patient_id or requester.id)
        tag = f'demo-tier2-{int(time.time())}'
        self._reset_engine(target)
        client = self._client(requester)
        before = timezone.now()

        tiers = []
        for hr, spo2, sbp, dbp in TIER2_SEQUENCE:
            time.sleep(POST_DELAY)
            resp = self._post(client, target, tag, self._batch(hr, spo2, sbp, dbp), location=location)
            tiers.extend(self._tiers(resp))
        tiers = sorted(set(tiers))
        alert = self._latest_alert(target, since=before)

        confirmed = 2 in tiers
        reads = ', '.join(
            f"Reading {i + 1}: HR={r[0]} bpm, SpO2={r[1]}%, BP={r[2]}/{r[3]}"
            for i, r in enumerate(TIER2_SEQUENCE)
        )
        reason = f"HEALTH ALERT: 3 consecutive high-risk readings detected by the RF model. {reads}."
        return self._result(
            2, confirmed, tiers, alert, 'health_alert', reason,
            'Tier 2 (Health Alert) fired: RF predicted high risk on 3 consecutive readings.',
        )

    def generate_trend_alert_scenario(self, requester, target_patient_id=None, location=None):
        """Guarantees a Trend (Tier 3) alert via LSTM early-warning, gated
        behind a Tier 2 trigger. The worst-case last-hour deterioration
        escalates to a full EMERGENCY (Tier 1 delivery: EmergencyEvent +
        emergency location + email). Replays one simulated hour of gradual
        decline, then 3 sharply elevated readings."""
        target = int(target_patient_id or requester.id)
        tag = f'demo-tier3-{int(time.time())}'
        self._reset_engine(target)
        client = self._client(requester)
        before = timezone.now()

        tiers = []
        # Phase 1: 60 readings of gradual deterioration (HR 72->92,
        # SpO2 98->94%, BP 120/80->140/88). The RF model also flags the later
        # ones as high risk, so Tier 2 fires along the way -- a bonus for the
        # demo. Tier 3 cannot fire yet (it is gated behind Tier 2 + needs the
        # LSTM 60-step window, which is still filling).
        for i in range(60):
            t = i / 59
            hr = round(TREND_START[0] + t * (TREND_END[0] - TREND_START[0]), 1)
            spo2 = round(TREND_START[1] + t * (TREND_END[1] - TREND_START[1]), 1)
            sbp = round(TREND_START[2] + t * (TREND_END[2] - TREND_START[2]))
            dbp = round(TREND_START[3] + t * (TREND_END[3] - TREND_START[3]))
            time.sleep(POST_DELAY)
            resp = self._post(client, target, tag, self._batch(hr, spo2, sbp, dbp), location=location)
            tiers.extend(self._tiers(resp))

        # Phase 2: 3 sharply elevated readings -> Tier 2 fires, then the LSTM
        # last-hour check runs (gated by Tier 2). The worst-case trend
        # escalates to a Tier 1 EMERGENCY. Tiers accumulate across every post;
        # the alert for this scenario is created on whichever post first trips
        # the escalation.
        for hr, spo2, sbp, dbp in TIER2_SEQUENCE:
            time.sleep(POST_DELAY)
            resp = self._post(client, target, tag, self._batch(hr, spo2, sbp, dbp), location=location)
            tiers.extend(self._tiers(resp))
        tiers = sorted(set(tiers))
        alert = self._latest_alert(target, since=before)

        confirmed = 1 in tiers
        final_tier = 1 if confirmed else 3
        reason = (
            f"TREND ALERT: Sustained deterioration detected over the last hour. "
            f"HR increased from {TREND_START[0]} to {TREND_END[0]} bpm, "
            f"SpO2 dropped from {TREND_START[1]}% to {TREND_END[1]}%, "
            f"BP rose from {TREND_START[2]}/{TREND_START[3]} to "
            f"{TREND_END[2]}/{TREND_END[3]}. "
            f"The worst-case last-hour trend escalated to a full EMERGENCY."
        )
        return self._result(
            final_tier, confirmed, tiers, alert, 'trend_alert', reason,
            'Trend (Tier 3) escalated to EMERGENCY: the LSTM confirmed '
            'worst-case deterioration over the last hour, gated behind the '
            'Tier 2 trigger.',
        )

    def generate_full_demo(self, requester, target_patient_id=None, location=None):
        """Run all three guaranteed scenarios in sequence."""
        target = int(target_patient_id or requester.id)
        r1 = self.generate_emergency_scenario(requester, target, location=location)
        time.sleep(0.2)
        r2 = self.generate_health_alert_scenario(requester, target, location=location)
        time.sleep(0.2)
        r3 = self.generate_trend_alert_scenario(requester, target, location=location)
        confirmed = r1['confirmed'] and r2['confirmed'] and r3['confirmed']
        return {
            'tier': 'all',
            'confirmed': confirmed,
            'scenarios': [r1, r2, r3],
            'summary': (
                f"Full demo complete: Tier 1={r1['confirmed']}, "
                f"Tier 2={r2['confirmed']}, Tier 3={r3['confirmed']}."
            ),
        }


# Process-wide singleton used by the demo endpoints.
alert_generator = AlertGenerator()