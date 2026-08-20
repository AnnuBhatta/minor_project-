"""
Unit tests for the Tier 1 (emergency) rule engine in
ml_models/alert_engine.py.

Covers:
  - Rule (a) single_threshold: every parameter's low AND high breach
  - Exactly 2 simultaneous breaches -> NO multi-parameter rule
  - Exactly 3 simultaneous breaches -> multi-parameter rule fires
  - All 5 breaches -> both rules fire cleanly
  - Fully normal vitals -> nothing fires

Run from the backend/ directory:
    .venv/Scripts/python -m unittest ml_models.test_alert_engine -v
"""
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

import unittest  # noqa: E402

from ml_models.alert_engine import (  # noqa: E402
    AlertEngine,
    TIER1_CRITICAL_THRESHOLDS,
    TIER1_MULTI_PARAMETER_MIN_COUNT,
)


def make_engine():
    return AlertEngine(user_id=99999)


NORMAL = {
    'heart_rate': 75,
    'oxygen_saturation': 97,
    'blood_pressure_systolic': 118,
    'blood_pressure_diastolic': 76,
    'derived_pulse_pressure': 42,
}


class Tier1SingleParameterRuleTest(unittest.TestCase):
    """Rule (a): any single parameter breach must fire immediately."""

    def assert_single_breach(self, param, value, expected_parameter):
        data = dict(NORMAL)
        data[param] = value
        alerts = make_engine().check_tier1_emergency(data)

        self.assertEqual(len(alerts), 1, f"expected 1 alert for {param}={value}, got {alerts}")
        alert = alerts[0]
        self.assertEqual(alert['triggered'], True)
        self.assertEqual(alert['tier'], 1)
        self.assertEqual(alert['severity'], 'critical')
        self.assertEqual(alert['rule'], 'single_threshold')
        breaches = alert['breaches']
        self.assertEqual(len(breaches), 1)
        self.assertEqual(breaches[0]['parameter'], expected_parameter)
        self.assertEqual(breaches[0]['value'], float(value))

    def test_heart_rate_low(self):
        self.assert_single_breach('heart_rate', 35, 'heart_rate')

    def test_heart_rate_high(self):
        self.assert_single_breach('heart_rate', 150, 'heart_rate')

    def test_oxygen_saturation_low(self):
        self.assert_single_breach('oxygen_saturation', 85, 'oxygen_saturation')

    def test_oxygen_saturation_has_no_upper_bound(self):
        # SpO2 > 100 is physically impossible but must NOT trip the "high"
        # branch because max is None -- only the low bound applies.
        alerts = make_engine().check_tier1_emergency({**NORMAL, 'oxygen_saturation': 101})
        self.assertEqual(len(alerts), 0)

    def test_systolic_low(self):
        self.assert_single_breach('blood_pressure_systolic', 70, 'blood_pressure_systolic')

    def test_systolic_high(self):
        self.assert_single_breach('blood_pressure_systolic', 190, 'blood_pressure_systolic')

    def test_diastolic_low(self):
        self.assert_single_breach('blood_pressure_diastolic', 45, 'blood_pressure_diastolic')

    def test_diastolic_high(self):
        self.assert_single_breach('blood_pressure_diastolic', 130, 'blood_pressure_diastolic')

    def test_pulse_pressure_low(self):
        self.assert_single_breach('derived_pulse_pressure', 15, 'derived_pulse_pressure')

    def test_pulse_pressure_high(self):
        self.assert_single_breach('derived_pulse_pressure', 80, 'derived_pulse_pressure')


class Tier1MultiParameterRuleTest(unittest.TestCase):
    """Rule (b): count-based multi-parameter critical alert."""

    def test_exactly_two_breaches_no_multi(self):
        data = {
            **NORMAL,
            'heart_rate': 150,                 # high breach
            'oxygen_saturation': 85,           # low breach
        }
        alerts = make_engine().check_tier1_emergency(data)

        rules = [a['rule'] for a in alerts]
        self.assertEqual(rules, ['single_threshold'])
        self.assertEqual(len(alerts[0]['breaches']), 2)
        self.assertNotIn('multi_parameter_count', rules)

    def test_exactly_three_breaches_triggers_multi(self):
        data = {
            **NORMAL,
            'heart_rate': 35,                  # low
            'oxygen_saturation': 85,           # low
            'blood_pressure_systolic': 190,    # high
        }
        alerts = make_engine().check_tier1_emergency(data)

        rules = [a['rule'] for a in alerts]
        self.assertIn('single_threshold', rules)
        self.assertIn('multi_parameter_count', rules)

        multi = next(a for a in alerts if a['rule'] == 'multi_parameter_count')
        self.assertEqual(multi['breach_count'], 3)
        self.assertEqual(multi['minimum_count'], TIER1_MULTI_PARAMETER_MIN_COUNT)
        self.assertEqual(multi['total_parameters'], len(TIER1_CRITICAL_THRESHOLDS))
        self.assertIn('Heart Rate', multi['breached_parameters'])
        self.assertIn('Oxygen Saturation', multi['breached_parameters'])
        self.assertIn('Systolic Blood Pressure', multi['breached_parameters'])
        self.assertIn('multi-parameter critical', multi['message'].lower())

    def test_all_five_breaches_fires_both_rules(self):
        data = {
            'heart_rate': 30,
            'oxygen_saturation': 80,
            'blood_pressure_systolic': 200,
            'blood_pressure_diastolic': 140,
            'derived_pulse_pressure': 10,
        }
        alerts = make_engine().check_tier1_emergency(data)

        rules = [a['rule'] for a in alerts]
        self.assertEqual(rules, ['single_threshold', 'multi_parameter_count'])

        single = alerts[0]
        self.assertEqual(len(single['breaches']), 5)

        multi = alerts[1]
        self.assertEqual(multi['breach_count'], 5)
        self.assertEqual(len(multi['breached_parameters']), 5)


class Tier1NormalCaseTest(unittest.TestCase):
    def test_normal_vitals_trigger_nothing(self):
        alerts = make_engine().check_tier1_emergency(NORMAL)
        self.assertEqual(alerts, [])

    def test_missing_parameter_is_ignored(self):
        # A missing vital (None/absent) must not be counted as a breach.
        data = {'heart_rate': 75, 'oxygen_saturation': 97}
        self.assertEqual(make_engine().check_tier1_emergency(data), [])


if __name__ == '__main__':
    unittest.main()