#!/bin/sh
set -e

echo "Waiting for database..."
python - <<'PY'
import os, time
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.db import connection
for _ in range(30):
    try:
        connection.ensure_connection()
        print("Database ready.")
        break
    except Exception as e:
        print(f"  waiting for db: {e}")
        time.sleep(2)
else:
    raise SystemExit("Database not reachable after 60s")
PY

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput || echo "collectstatic skipped"

echo "Starting Daphne (ASGI) on :8000 — WebSockets enabled."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application