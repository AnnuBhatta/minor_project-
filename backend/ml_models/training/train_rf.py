"""
Retrains the Random Forest snapshot risk classifier.

Why this exists: the .joblib model shipped with the project returns the
same prediction (~99.6% high risk) for every input regardless of vitals --
verified by sweeping heart rate 40-160, SpO2 70-99, age 5-100 and BMI 15-40
independently and seeing zero change in output. That model is unusable for
a live demo. This script trains a fresh RandomForestClassifier on a
synthetic but clinically-grounded dataset, using the same 6 features and
column names the rest of the codebase already expects:
    Heart Rate, Oxygen Saturation, Systolic Blood Pressure,
    Diastolic Blood Pressure, Derived_HR, Derived_Pulse_Pressure

Class encoding (used everywhere in the app):
    label 1 = "High Risk", label 0 = "Low Risk"
so probability[:, 1] is the high-risk probability.

Run with:  <venv>/bin/python ml_models/training/train_rf.py
(no Django needed -- pure sklearn/numpy/pandas)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import OrdinalEncoder

FEATURE_COLUMNS = [
    'Heart Rate', 'Oxygen Saturation',
    'Systolic Blood Pressure', 'Diastolic Blood Pressure',
    'Derived_HR', 'Derived_Pulse_Pressure',
]

# label 1 = "High Risk", label 0 = "Low Risk"
RISK_LABELS = ['Low Risk', 'High Risk']


def risk_score(hr, spo2, sys_bp, dia_bp):
    """A soft, clinically-informed scoring rule used only to LABEL the
    synthetic training data (not used at inference time -- the RF learns
    its own decision boundary from this). Mirrors the normal ranges used
    elsewhere in the app (vitals/views.py:_risk_category)."""
    score = 0.0
    if hr < 50 or hr > 120:
        score += 2.0
    elif hr < 55 or hr > 110:
        score += 0.8
    if spo2 < 90:
        score += 2.5
    elif spo2 < 94:
        score += 1.0
    if sys_bp < 80 or sys_bp > 180 or dia_bp < 50 or dia_bp > 120:
        score += 2.0
    elif sys_bp > 150 or dia_bp > 95:
        score += 0.8
    return score


def make_row(rng, force_high=None):
    """Sample one synthetic patient snapshot. force_high=True/False biases
    sampling toward that class so the dataset is roughly balanced;
    force_high=None samples uniformly at random (realistic mixed case)."""
    if force_high is True:
        hr = rng.choice([rng.uniform(20, 49), rng.uniform(121, 190)]) if rng.random() < 0.55 else rng.normal(78, 10)
        spo2 = rng.uniform(70, 92) if rng.random() < 0.5 else rng.normal(96, 2)
        sys_bp = rng.choice([rng.uniform(60, 79), rng.uniform(181, 220)]) if rng.random() < 0.4 else rng.normal(118, 10)
        dia_bp = rng.choice([rng.uniform(30, 49), rng.uniform(121, 140)]) if rng.random() < 0.3 else rng.normal(76, 8)
    elif force_high is False:
        hr = np.clip(rng.normal(75, 10), 55, 110)
        spo2 = np.clip(rng.normal(97, 1.2), 94, 100)
        sys_bp = np.clip(rng.normal(115, 10), 90, 148)
        dia_bp = np.clip(rng.normal(75, 7), 55, 92)
    else:
        hr = rng.uniform(35, 190)
        spo2 = rng.uniform(75, 100)
        sys_bp = rng.uniform(65, 220)
        dia_bp = rng.uniform(35, 140)

    score = risk_score(hr, spo2, sys_bp, dia_bp)
    label = 1 if score >= 1.8 else 0  # 1 = High Risk, 0 = Low Risk
    return {
        'Heart Rate': round(hr, 1),
        'Oxygen Saturation': round(spo2, 1),
        'Systolic Blood Pressure': round(sys_bp, 1),
        'Diastolic Blood Pressure': round(dia_bp, 1),
        'Derived_HR': round(float(rng.uniform(0.0, 1.0)), 4),
        'Derived_Pulse_Pressure': round(sys_bp - dia_bp, 2),
        'label': label,
    }


def build_dataset(n=6000, seed=11):
    rng = np.random.default_rng(seed)
    rows = []
    # Mix of clearly-normal, clearly-abnormal, and unbiased/random cases so
    # the model learns real decision boundaries instead of a single class.
    for _ in range(n // 3):
        rows.append(make_row(rng, force_high=False))
    for _ in range(n // 3):
        rows.append(make_row(rng, force_high=True))
    for _ in range(n - 2 * (n // 3)):
        rows.append(make_row(rng, force_high=None))
    df = pd.DataFrame(rows)
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


def train():
    df = build_dataset()
    print('Class balance:\n', df['label'].value_counts(normalize=True))

    X = df[FEATURE_COLUMNS]
    y = df['label']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=11, stratify=y)

    model = RandomForestClassifier(
        n_estimators=300, max_depth=10, min_samples_leaf=3,
        class_weight='balanced', random_state=11, n_jobs=-1,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    print(f"Test accuracy: {accuracy_score(y_test, preds):.4f}")
    print(classification_report(y_test, preds))
    print('feature_importances_:', dict(zip(model.feature_names_in_, model.feature_importances_.round(3))))

    return model


def sanity_check(model):
    """Confirm the model actually responds to inputs (the bug we're fixing)
    and that probability[:, 1] is the high-risk probability."""
    normal = pd.DataFrame([{
        'Heart Rate': 72, 'Oxygen Saturation': 98,
        'Systolic Blood Pressure': 115, 'Diastolic Blood Pressure': 75,
        'Derived_HR': 0.1, 'Derived_Pulse_Pressure': 40,
    }])[FEATURE_COLUMNS]
    critical = pd.DataFrame([{
        'Heart Rate': 155, 'Oxygen Saturation': 82,
        'Systolic Blood Pressure': 195, 'Diastolic Blood Pressure': 118,
        'Derived_HR': 0.1, 'Derived_Pulse_Pressure': 77,
    }])[FEATURE_COLUMNS]
    p_normal = model.predict_proba(normal)[0][1]      # index 1 = high risk
    p_critical = model.predict_proba(critical)[0][1]
    print(f"Sanity check -- normal vitals high-risk prob: {p_normal:.3f}, critical vitals: {p_critical:.3f}")
    assert p_normal < 0.3, "Model still flags normal vitals as high risk -- do not ship"
    assert p_critical > 0.7, "Model does not flag clearly critical vitals -- do not ship"
    print("Sanity check passed: model responds correctly to inputs.")


if __name__ == '__main__':
    model = train()
    sanity_check(model)
    out_path = Path(__file__).resolve().parent.parent / 'models' / 'rf_risk_model.joblib'
    import joblib
    joblib.dump(model, out_path)

    encoder = OrdinalEncoder(categories=[RISK_LABELS])  # 0='Low Risk', 1='High Risk'
    encoder.fit(np.array(RISK_LABELS).reshape(-1, 1))
    enc_path = Path(__file__).resolve().parent.parent / 'encoders' / 'label_encoder.joblib'
    joblib.dump(encoder, enc_path)

    print(f"Saved retrained model to {out_path}")
    print(f"Saved label encoder to {enc_path}  (classes: {list(encoder.categories_[0])})")