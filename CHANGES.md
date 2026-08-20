# What changed in this pass

## Bugs found and fixed
1. **RF feature mismatch** — `ml_models/features/feature_config.json` listed 6 features;
   the trained model expects 7 in a specific order (`Age, Heart Rate, Body Temperature,
   Oxygen Saturation, Systolic BP, Diastolic BP, Derived_BMI`). Every prediction call was
   silently failing. Fixed the config and added
   `prediction_service.build_features_from_vitals()` to assemble these automatically from
   a patient's profile + latest readings.
2. **Broken Random Forest model** — the shipped `.joblib` returned the same ~99.6%
   high-risk output for every input regardless of vitals (verified by sweeping age,
   heart rate, SpO2, BMI independently). Retrained from scratch on a synthetic,
   balanced dataset (`ml_models/training/train_rf.py`) — 99.4% test accuracy, and a
   sanity check confirms it correctly separates normal vitals (score 0.8) from
   critical vitals (score 99.5).
3. **`numpy==a1.26.4`** typo in `requirements.txt` — fixed. Also pinned
   `scikit-learn==1.6.1` to match what the retrained model was built with.
4. **`.env` / `firebase-adminsdk.json` committed as plaintext secrets** — removed from
   the zip, added `.env.example` and `.gitignore`. **Rotate both keys before pushing
   anywhere public — the ones in the original zip are no longer trustworthy.**

## New backend functionality (mapped to the 7 requirements)
1. **`/api/readings/ingest/`** (`vitals/views.py: VitalReadingIngestView`) — source-agnostic,
   accepts a single reading or a batch, tags `source: simulated|device|manual`
   (new field on `VitalSign`, migration `vitals/0002_...`).
2. **Inference on arrival** (`vitals/inference.py`) — every ingest call runs the RF
   snapshot classifier and, once 10 heart-rate readings exist, the LSTM trend model
   over the last 20-minute window.
3. **LSTM early-warning model** — built from scratch in pure NumPy
   (`ml_models/lstm/model.py`, trained by `ml_models/training/train_lstm.py`) since the
   project had no LSTM at all before. 100% validation accuracy on synthetic
   deteriorating-vs-stable windows; confirmed it flags a rising-heart-rate trend before
   the RF alone would.
4. **Alerting** — both models create `Alert` records on threshold crossing
   (`vitals/inference.py:_create_alert`).
5. **Caregiver dashboard chart** — `GET /api/vitals/daily-chart/` returns daily mean+peak
   heart rate, `%time_in_high_risk`, alert markers, and episode count/duration — all
   derived from the same `Prediction` records that trigger alerts, so the chart can
   never contradict its own markers. Rendered in `frontend/src/components/CaregiverChart.jsx`.
6. **Demo controls** — `demo/` app: fixed scenario (deterministic, repeatable) and
   random scenario (different story + severity every run) both run in a background
   thread that POSTs to the *real* ingest endpoint via DRF's `APIClient`, tick by tick —
   not a shortcut that calls the inference pipeline directly. Buttons in
   `frontend/src/components/DemoControls.jsx`.
7. **Patient/session management** — reused the existing guardian/patient relationship
   on `accounts.User`. Added `GET /api/auth/my-patients/` and a `patient_id` query
   param on all read endpoints (with a 403 if you're not that patient's guardian).
   `frontend/src/contexts/PatientContext.jsx` + `PatientSelector.jsx`.

## What was already solid and untouched
- Live location map (Leaflet + OpenStreetMap — free, no API key) in
  `LiveLocationTracker.jsx` / `EmergencyDashboard.jsx`.
- WebSocket emergency broadcast to guardians (`location` app).
- FCM push notification wiring.
- 5-second polling on the main dashboard.

## Still worth doing if you have time left
- The LSTM/RF are trained on **synthetic** data — good enough to prove the
  architecture and demo convincingly, but if your course wants real clinical data,
  retrain on that instead (both training scripts are self-contained and reusable).
- No automated test suite exists yet — the verification in this pass was done manually
  via Django's test client; consider adding a `tests.py` per app before submission if
  your rubric checks for it.
- `channels-redis` is in `requirements.txt` for the WebSocket layer channel backend;
  confirm `CHANNEL_LAYERS` in `settings.py` points at a Redis instance you actually have
  running, or fall back to the in-memory channel layer for local dev/demo.
