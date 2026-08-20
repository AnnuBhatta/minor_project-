"""
Scenario definitions for the demo controls.

A scenario is just a list of "ticks", each tick being a dict of vital
readings that get POSTed together to /api/readings/ingest/ with
source='simulated'. The runner (runner.py) walks through this list on a
timer, exactly the way a real watch would stream readings -- the ingest
endpoint and inference pipeline don't know or care that the data came from
here.

FIXED_SCENARIO is deterministic and reproducible -- good for a repeatable
demo walkthrough ("watch it catch this exact deterioration every time").

generate_random_scenario() builds a new, unpredictable scenario on each
call -- this is the "prove it's not just hardcoded" button: every run picks
a different story and different numbers, but the same pipeline (RF + LSTM +
alerting) has to correctly handle whatever it's given.
"""
import random


def _tick(heart_rate=None, spo2=None, systolic=None, diastolic=None, temperature=None):
    readings = []
    if heart_rate is not None:
        readings.append({'vital_type': 'heart_rate', 'value': {'heart_rate': round(heart_rate)}})
    if spo2 is not None:
        readings.append({'vital_type': 'oxygen_saturation', 'value': {'spo2': round(spo2, 1)}})
    if systolic is not None and diastolic is not None:
        readings.append({
            'vital_type': 'blood_pressure',
            'value': {'systolic': round(systolic), 'diastolic': round(diastolic)},
        })
    if temperature is not None:
        readings.append({'vital_type': 'temperature', 'value': {'temperature': round(temperature, 1)}})
    return readings


def _build_fixed_scenario():
    """
    A ~1-hour story told in 2-minute ticks (30 ticks):
      ticks 0-9:   stable baseline
      ticks 10-19: gradual tachycardia + falling SpO2 (the LSTM should
                   catch this as an early warning before any single
                   reading looks critical)
      ticks 20-24: crosses into RF 'high risk' territory (both models
                   should now agree)
      ticks 25-29: recovers back toward baseline
    """
    ticks = []
    for i in range(10):
        ticks.append(_tick(heart_rate=75 + (i % 3), spo2=97.5, systolic=116, diastolic=75, temperature=36.7))
    for i in range(10):
        progress = i / 9
        ticks.append(_tick(
            heart_rate=76 + progress * 42,
            spo2=97.5 - progress * 6,
            systolic=116 + progress * 10,
            diastolic=75 + progress * 6,
            temperature=36.7 + progress * 0.4,
        ))
    for i in range(5):
        ticks.append(_tick(heart_rate=138 + i, spo2=89 - i * 0.4, systolic=150, diastolic=95, temperature=37.4))
    for i in range(5):
        progress = i / 4
        ticks.append(_tick(
            heart_rate=140 - progress * 60,
            spo2=88 + progress * 9,
            systolic=150 - progress * 32,
            diastolic=95 - progress * 18,
            temperature=37.4 - progress * 0.6,
        ))
    return ticks


FIXED_SCENARIO = _build_fixed_scenario()


def generate_random_scenario(n_ticks=None, rng=None):
    """Builds a fresh, randomized scenario every call. Picks one of several
    story shapes and randomizes its severity/timing so back-to-back demo
    runs never look identical."""
    rng = rng or random.Random()
    n_ticks = n_ticks or rng.randint(20, 34)
    story = rng.choice(['stable', 'tachycardia', 'bradycardia', 'hypoxia', 'hypertensive_crisis', 'sudden_event'])

    base_hr = rng.uniform(68, 84)
    base_spo2 = rng.uniform(96, 99)
    base_sys = rng.uniform(108, 122)
    base_dia = rng.uniform(70, 80)
    base_temp = rng.uniform(36.4, 37.0)

    ticks = []
    onset = rng.randint(n_ticks // 4, n_ticks // 2)
    severity = rng.uniform(0.6, 1.4)

    for i in range(n_ticks):
        jitter_hr = rng.uniform(-3, 3)
        jitter_spo2 = rng.uniform(-0.4, 0.4)
        jitter_bp = rng.uniform(-4, 4)

        if story == 'stable' or i < onset:
            hr, spo2, sys_bp, dia_bp, temp = base_hr, base_spo2, base_sys, base_dia, base_temp
        else:
            progress = min(1.0, (i - onset) / max(1, (n_ticks - onset - 1))) * severity
            if story == 'tachycardia':
                hr = base_hr + progress * 65
                spo2, sys_bp, dia_bp, temp = base_spo2, base_sys, base_dia, base_temp
            elif story == 'bradycardia':
                hr = base_hr - progress * 40
                spo2, sys_bp, dia_bp, temp = base_spo2, base_sys, base_dia, base_temp
            elif story == 'hypoxia':
                spo2 = base_spo2 - progress * 15
                hr = base_hr + progress * 12
                sys_bp, dia_bp, temp = base_sys, base_dia, base_temp
            elif story == 'hypertensive_crisis':
                sys_bp = base_sys + progress * 70
                dia_bp = base_dia + progress * 40
                hr = base_hr + progress * 15
                spo2, temp = base_spo2, base_temp
            else:  # sudden_event: jumps rather than drifts, once onset hits
                jump = 1.0 if i >= onset else 0.0
                hr = base_hr + jump * rng.uniform(45, 75)
                spo2 = base_spo2 - jump * rng.uniform(8, 16)
                sys_bp, dia_bp, temp = base_sys, base_dia, base_temp + jump * rng.uniform(0.3, 1.0)

        ticks.append(_tick(
            heart_rate=hr + jitter_hr,
            spo2=max(70, spo2 + jitter_spo2),
            systolic=sys_bp + jitter_bp,
            diastolic=dia_bp + jitter_bp * 0.6,
            temperature=temp,
        ))

    return {'story': story, 'n_ticks': n_ticks, 'onset_tick': onset, 'ticks': ticks}


def continuous_ticks():
    """Yields simulated tick readings forever, cycling through
    normal -> gradual deterioration -> critical -> recovery phases so the
    dashboard always has live data and the alert tiers fire naturally over
    time (no smartwatch required). The runner thread walks this generator
    until stopped."""
    while True:
        # Phase 1: stable baseline
        for i in range(25):
            yield _tick(
                heart_rate=76 + (i % 4), spo2=97.5,
                systolic=116, diastolic=75, temperature=36.7,
            )
        # Phase 2: gradual deterioration (tachycardia + falling SpO2) --
        # the LSTM trend signal should pick this up first.
        for i in range(15):
            p = i / 14
            yield _tick(
                heart_rate=78 + p * 60,
                spo2=97.5 - p * 8,
                systolic=118 + p * 30,
                diastolic=76 + p * 20,
                temperature=36.7 + p * 0.5,
            )
        # Phase 3: critical -- 3+ vitals out of range (HR>140, SpO2<90,
        # SYS>180, pulse pressure>70) -> Tier 1 emergency fires.
        for i in range(2):
            yield _tick(
                heart_rate=150 + i, spo2=85,
                systolic=190, diastolic=115, temperature=38.0,
            )
        # Phase 4: recovery back toward baseline
        for i in range(12):
            p = i / 11
            yield _tick(
                heart_rate=150 - p * 75,
                spo2=85 + p * 13,
                systolic=190 - p * 75,
                diastolic=115 - p * 40,
                temperature=38.0 - p * 1.2,
            )
