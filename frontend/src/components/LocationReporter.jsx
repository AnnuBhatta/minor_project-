import { useState, useEffect, useRef, useCallback } from 'react';

/*
 * LocationReporter
 *
 * Continuously reports the patient's real browser GPS to
 * POST /api/location/update/, so the alert engine always has a real
 * latitude/longitude to attach to every alert and emergency.
 *
 * Without this, `UserLocation` stays empty and alerts fall back to
 * lat/lng = 0/0 (and the guardian sees no live location).
 *
 * Geolocation works on localhost (a secure context). If the browser blocks
 * the permission request, the card shows the error so it's obvious.
 */
const LocationReporter = () => {
  const [location, setLocation] = useState(null);
  const [status, setStatus] = useState('idle'); // idle | tracking | denied | error | unsupported
  const [error, setError] = useState(null);
  const watchIdRef = useRef(null);
  const lastSentRef = useRef(0);

  const sendToBackend = useCallback(async (coords) => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) return;
      const res = await fetch('/api/location/update/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          latitude: coords.latitude,
          longitude: coords.longitude,
          accuracy: coords.accuracy ?? null,
          altitude: coords.altitude ?? null,
          speed: coords.speed ?? null,
          heading: coords.heading ?? null,
          is_emergency: false,
        }),
      });
      if (!res.ok) throw new Error(`location/update: ${res.status}`);
    } catch (e) {
      console.error('[LOC-REPORT] send failed:', e);
    }
  }, []);

  const start = useCallback(() => {
    if (!navigator.geolocation) {
      setStatus('unsupported');
      setError('Geolocation is not supported by this browser.');
      return;
    }
    setStatus('tracking');
    setError(null);

    watchIdRef.current = navigator.geolocation.watchPosition(
      (position) => {
        const { latitude, longitude, accuracy, altitude, speed, heading } = position.coords;
        const now = Date.now();
        setLocation({ latitude, longitude, accuracy, timestamp: position.timestamp });
        // Throttle backend writes to once per second (watchPosition can fire
        // many times a second on some devices).
        if (now - lastSentRef.current > 1000) {
          lastSentRef.current = now;
          sendToBackend({ latitude, longitude, accuracy, altitude, speed, heading });
        }
      },
      (err) => {
        console.error('[LOC-REPORT] geolocation error:', err);
        if (err.code === err.PERMISSION_DENIED) {
          setStatus('denied');
          setError('Location permission denied. Allow location access so alerts can include your position.');
        } else {
          setStatus('error');
          setError(`Error getting location: ${err.message}`);
        }
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 }
    );
  }, [sendToBackend]);

  const stop = useCallback(() => {
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    setStatus('idle');
  }, []);

  useEffect(() => {
    start();
    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
      }
    };
  }, [start]);

  return (
    <div className="location-reporter">
      <div className="lr-row">
        <span className={`lr-dot ${status === 'tracking' ? 'active' : 'off'}`} />
        <span className="lr-text">
          {status === 'tracking' && location
            ? `📡 Reporting live location: ${location.latitude.toFixed(5)}, ${location.longitude.toFixed(5)}`
            : status === 'tracking'
              ? '📡 Locating you…'
              : status === 'denied'
                ? '🚫 Location denied — alerts will have no real position'
                : status === 'unsupported'
                  ? '🚫 Geolocation unsupported in this browser'
                  : status === 'error'
                    ? '⚠️ Location unavailable'
                    : '📍 Location reporting stopped'}
        </span>
        <button type="button" className="lr-btn" onClick={status === 'tracking' ? stop : start}>
          {status === 'tracking' ? 'Stop' : 'Start'}
        </button>
      </div>
      {error && <div className="lr-error">{error}</div>}
      {status === 'tracking' && location?.accuracy != null && (
        <div className="lr-accuracy">Accuracy ≈ {Math.round(location.accuracy)} m</div>
      )}
      <style>{`
        .location-reporter {
          background: #f0f9f4;
          border: 1px solid #cfe8d7;
          border-radius: 8px;
          padding: 8px 12px;
          margin-bottom: 16px;
          font-size: 13px;
          color: #2e5e3c;
        }
        .lr-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .lr-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
        .lr-dot.active { background: #2f9e44; animation: lrPulse 1.5s infinite; }
        .lr-dot.off { background: #adb5bd; }
        @keyframes lrPulse { 50% { opacity: 0.4; } }
        .lr-text { flex: 1; min-width: 180px; }
        .lr-btn {
          padding: 3px 12px; border: 1px solid #2f9e44; background: #2f9e44;
          color: white; border-radius: 4px; cursor: pointer; font-size: 12px;
        }
        .lr-error { margin-top: 4px; color: #c0392b; }
        .lr-accuracy { margin-top: 2px; font-size: 12px; color: #5c7c63; }
      `}</style>
    </div>
  );
};

export default LocationReporter;