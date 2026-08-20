# Deployment Guide — VitalWatch (Django + React + Channels)

This guide deploys the full stack with Docker: **React (nginx) → Django (Daphne) → PostgreSQL + Redis**, so all three real-time features work in production:

1. **Live alerts** (WebSocket over `/ws/alerts/`)
2. **Push notifications** (Firebase Cloud Messaging)
3. **Live location** (browser geolocation → `/api/location/update/` → `/ws/location/`)

---

## 1. Prerequisites

- Docker + Docker Compose installed on the host (or deploy the same stack on Render / Railway / any VPS with Docker).
- A domain + TLS for geolocation and FCM to work. `localhost` is exempt; **production must be HTTPS**.

---

## 2. Firebase setup (only needed for push notifications)

1. Go to https://console.firebase.google.com → **Add project**.
2. Register a **Web app** → copy its config (`apiKey`, `authDomain`, `projectId`, `storageBucket`, `messagingSenderId`, `appId`).
3. Project settings → **Cloud Messaging** → copy the **Web Push certificates → Key pair** (VAPID key).
4. Project settings → **Service accounts** → **Generate new private key** → save `firebase-adminsdk.json`.

Then populate `.env` (see below) with these values.

> The backend code (`emergency/services.py`) supports credentials via **either** the `FIREBASE_*` env vars **or** a mounted `firebase-adminsdk.json`. The frontend (`frontend/src/firebase.js`) skips FCM gracefully when the `VITE_FIREBASE_*` values are missing.

---

## 3. Environment file

```bash
cp .env.example .env
```

Fill in at minimum:

```dotenv
DJANGO_SECRET_KEY=<random string>
POSTGRES_PASSWORD=<strong password>
FRONTEND_URL=https://yourdomain.com        # when you have TLS
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
# email…
EMAIL_HOST_USER=you@gmail.com
EMAIL_HOST_PASSWORD=<Gmail app password>
# firebase backend…
FIREBASE_PROJECT_ID=…
FIREBASE_PRIVATE_KEY=…                    # single line, \n escapes ok
FIREBASE_CLIENT_EMAIL=…
# firebase frontend (Docker build args)…
VITE_FIREBASE_API_KEY=…
VITE_FIREBASE_APP_ID=…
VITE_FIREBASE_VAPID_KEY=…
```

---

## 4. Build & run

```bash
docker compose up --build -d
```

- Frontend: `http://<host>` (nginx serves the React build)
- Backend/API: proxied from `/api/` and `/ws/` by nginx to Daphne on port 8000
- `backend` container auto-runs: wait-for-db → `migrate` → `collectstatic` → `daphne config.asgi:application`
- The ML models + dataset are baked into the image (models ~20 MB, CSV ~17 MB)

Useful commands:

```bash
docker compose logs -f backend      # watch migrations + FCM/alert logs
docker compose logs -f frontend     # nginx access logs
docker compose exec backend python manage.py createsuperuser
docker compose down                 # stop (data persists in the pgdata volume)
docker compose down -v              # stop AND wipe the database
```

---

## 5. HTTPS (required for live location + FCM)

The nginx container listens on port 80. Put a TLS terminator in front of it:

- **Caddy** (simplest — automatic Let's Encrypt):

  ```
  yourdomain.com {
      reverse_proxy localhost:80
  }
  ```

- Or a cloud load balancer (Render/Railway/AWS) that terminates TLS and forwards to port 80.

Once TLS is in place, set in `.env`:

```dotenv
FRONTEND_URL=https://yourdomain.com
ALLOWED_HOSTS=yourdomain.com
SECURE_SSL_REDIRECT=True
```

---

## 6. Verify the three features

After `docker compose up --build -d`:

1. **Live alerts** — open the app in two browsers: patient (e.g. `shreya`) and guardian (e.g. `Kavita`, approved link). On the patient page click **🚨 MANUAL EMERGENCY**; the guardian page shows the alert card instantly with the **● Live** pill connected.
2. **Push notification** — accept the browser notification permission when the app asks; open a second browser as the guardian and confirm the push arrives (requires the Firebase env vars + HTTPS).
3. **Live location** — on the patient dashboard allow location; the green card shows `📡 Reporting live location…`. On the guardian dashboard the **📍 Live Location** map shows the patient's marker + trail, updating every 3 s.

---

## 7. Notes & troubleshooting

- **WebSockets require Daphne (ASGI).** Do not use `runserver` or gunicorn alone — run `daphne config.asgi:application` (the container does this).
- **Redis channel layer.** `REDIS_URL` is set to the compose `redis` service, so real-time broadcasts work across processes. Without Redis the code falls back to in-memory, which only works on a single process.
- **Database.** `settings.py` uses SQLite when `DATABASE_URL` is unset (local dev) and PostgreSQL when set (Docker). Data lives in the `pgdata` volume.
- **Firebase token expiry.** FCM device tokens can expire/rotate; users who stop getting pushes should re-open the app once so the new token is registered.
- **Geolocation on desktop demo.** Chrome DevTools → Sensors → Override geolocation lets you simulate movement; the guardian map updates within ~3 s.

### Local development (unchanged)

```bash
# backend (Windows venv)
cd backend && .venv/Scripts/python.exe manage.py runserver

# frontend
cd frontend && npm run dev
```

Vite proxies `/api` and `/ws` to the backend, so everything works on `localhost` as before.