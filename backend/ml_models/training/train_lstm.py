"""
Trains the LSTM early-warning model on a synthetic dataset of 2-minute-
interval vital sign windows, and saves the resulting weights to
ml_models/models/lstm_trend_model.npz.

Run with:  python manage.py shell -c "exec(open('ml_models/training/train_lstm.py').read())"
or simply: python ml_models/training/train_lstm.py   (from the backend/ directory,
           with the venv's numpy on the path — no Django needed for this script).

What it does
------------
1. Generates synthetic 10-step (20-minute) windows of [heart_rate, spo2,
   systolic_bp, diastolic_bp] readings, 2 minutes apart, mimicking two kinds
   of patients:
     - stable:        vitals fluctuate mildly within a normal range the
                       whole window                              -> label 0
     - deteriorating:  vitals start near-normal and drift toward a risk
                       threshold across the window (this is exactly the
                       "early warning" pattern a single latest-reading
                       classifier like the Random Forest cannot see)
                                                                    -> label 1
   A flat-already-high-risk case and a noisy-but-non-trending case are also
   included so the model has to learn the *trend*, not just the final value.
2. Normalizes each feature to [0, 1] using fixed physiological bounds.
3. Trains a NumpyLSTM (see ml_models/lstm/model.py) with plain SGD + BPTT.
4. Reports train/validation accuracy and saves the trained weights.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ml_models.lstm.model import NumpyLSTM  # noqa: E402

FEATURE_BOUNDS = {
    'heart_rate': (40.0, 180.0),
    'spo2': (70.0, 100.0),
    'systolic_bp': (70.0, 200.0),
    'diastolic_bp': (40.0, 130.0),
}
WINDOW = 10


def normalize(window):
    """window: (10, 4) raw values in order [hr, spo2, sys, dia] -> (10, 4) in [0, 1]."""
    out = np.zeros_like(window, dtype=float)
    for idx, key in enumerate(FEATURE_BOUNDS):
        lo, hi = FEATURE_BOUNDS[key]
        out[:, idx] = np.clip((window[:, idx] - lo) / (hi - lo), 0.0, 1.0)
    return out


def make_stable_window(rng):
    hr = rng.normal(75, 6, WINDOW).clip(58, 105)
    spo2 = rng.normal(97, 1.0, WINDOW).clip(94, 100)
    sys_bp = rng.normal(115, 8, WINDOW).clip(90, 138)
    dia_bp = rng.normal(75, 6, WINDOW).clip(55, 88)
    return np.stack([hr, spo2, sys_bp, dia_bp], axis=1), 0


def make_deteriorating_window(rng):
    """Starts near-normal, drifts toward one or more risk thresholds by the
    end of the 20-minute window (heart rate racing/dropping, spo2 falling,
    or blood pressure drifting out of range)."""
    mode = rng.choice(['tachycardia', 'bradycardia', 'hypoxia', 'hypertension', 'hypotension'])
    t = np.linspace(0, 1, WINDOW)
    noise = lambda scale: rng.normal(0, scale, WINDOW)

    hr = 78 + noise(3)
    spo2 = 97 + noise(0.6)
    sys_bp = 115 + noise(5)
    dia_bp = 75 + noise(4)

    if mode == 'tachycardia':
        hr = 78 + t * rng.uniform(45, 70) + noise(3)
    elif mode == 'bradycardia':
        hr = 78 - t * rng.uniform(35, 50) + noise(3)
    elif mode == 'hypoxia':
        spo2 = 97 - t * rng.uniform(10, 16) + noise(0.5)
    elif mode == 'hypertension':
        sys_bp = 115 + t * rng.uniform(45, 80) + noise(4)
        dia_bp = 75 + t * rng.uniform(25, 45) + noise(3)
    elif mode == 'hypotension':
        sys_bp = 115 - t * rng.uniform(35, 55) + noise(4)
        dia_bp = 75 - t * rng.uniform(20, 35) + noise(3)

    return np.stack([hr, spo2, sys_bp, dia_bp], axis=1), 1


def make_already_high_flat_window(rng):
    """Already at a high-risk plateau for the whole window (no real trend,
    but still a case the model should flag)."""
    hr = rng.normal(rng.choice([135, 42]), 4, WINDOW)
    spo2 = rng.normal(86, 1.5, WINDOW).clip(75, 89)
    sys_bp = rng.normal(190, 6, WINDOW)
    dia_bp = rng.normal(115, 5, WINDOW)
    # Pick one abnormal channel at random, keep the rest normal.
    channel = rng.integers(0, 4)
    base = np.stack([
        rng.normal(75, 5, WINDOW), rng.normal(97, 1, WINDOW),
        rng.normal(115, 6, WINDOW), rng.normal(75, 5, WINDOW),
    ], axis=1)
    base[:, channel] = [hr, spo2, sys_bp, dia_bp][channel]
    return base, 1


def make_noisy_stable_window(rng):
    """Larger noise but no directional trend and stays in-range -> label 0.
    Prevents the model from learning 'any variance = risk'."""
    hr = 80 + rng.normal(0, 8, WINDOW)
    spo2 = (96.5 + rng.normal(0, 1.2, WINDOW)).clip(93, 100)
    sys_bp = 118 + rng.normal(0, 10, WINDOW)
    dia_bp = 76 + rng.normal(0, 7, WINDOW)
    return np.stack([hr, spo2, sys_bp, dia_bp], axis=1), 0


def build_dataset(n_per_class, seed=7):
    rng = np.random.default_rng(seed)
    generators = [
        (make_stable_window, n_per_class),
        (make_noisy_stable_window, n_per_class // 2),
        (make_deteriorating_window, n_per_class),
        (make_already_high_flat_window, n_per_class // 2),
    ]
    X, y = [], []
    for gen, count in generators:
        for _ in range(count):
            window, label = gen(rng)
            X.append(normalize(window))
            y.append(label)
    X = np.array(X)
    y = np.array(y)
    idx = rng.permutation(len(X))
    return X[idx], y[idx]


def train(epochs=6, lr=0.05, n_per_class=500, seed=7):
    X, y = build_dataset(n_per_class, seed=seed)
    split = int(len(X) * 0.85)
    X_train, y_train = X[:split], y[:split]
    X_val, y_val = X[split:], y[split:]

    model = NumpyLSTM(input_size=4, hidden_size=16, seed=42)

    for epoch in range(1, epochs + 1):
        order = np.random.default_rng(epoch).permutation(len(X_train))
        total_loss = 0.0
        for idx in order:
            total_loss += model.train_step(X_train[idx], y_train[idx], lr=lr)
        train_acc = evaluate(model, X_train, y_train)
        val_acc = evaluate(model, X_val, y_val)
        print(f"epoch {epoch}/{epochs}  loss={total_loss / len(X_train):.4f}  "
              f"train_acc={train_acc:.3f}  val_acc={val_acc:.3f}")

    return model, evaluate(model, X_val, y_val)


def evaluate(model, X, y):
    correct = 0
    for xi, yi in zip(X, y):
        prob = model.predict_proba(xi)
        correct += int((prob >= 0.5) == bool(yi))
    return correct / len(X)


if __name__ == '__main__':
    model, val_acc = train()
    out_path = Path(__file__).resolve().parent.parent / 'models' / 'lstm_trend_model.npz'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(out_path)
    print(f"Saved trained LSTM to {out_path} (final val_acc={val_acc:.3f})")
