import { useEffect, useRef, useState } from 'react';
import api from '../api';

/*
 * Turbo demo controls -- FAST dataset replay for presentations.
 *
 * Replays the real training dataset (vital_signs_dataset.csv) at a fast,
 * configurable cadence -- 100 readings at 1s = ~100 seconds (1.7 minutes) --
 * through the live ingest pipeline. Every reading runs RF + LSTM + the
 * three-tier alert system and is pushed over WebSocket to the patient and
 * guardian dashboards, exactly like a real smartwatch hit.
 *
 * The backend auto-selects a dataset patient whose readings contain
 * high-risk segments so alerts fire naturally during the demo.
 */

const SPEED_OPTIONS = [
  { label: '1 sec', value: 1 },
  { label: '2 sec', value: 2 },
  { label: '5 sec', value: 5 },
];

const COUNT_OPTIONS = [50, 100, 200];

const fmt = (secs) => {
  if (secs == null || !Number.isFinite(secs)) return '—';
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
};

export default function TurboDemoControls() {
  const [status, setStatus] = useState(null);
  const [speed, setSpeed] = useState(1);
  const [count, setCount] = useState(100);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  const pollStatus = async () => {
    try {
      const res = await api.get('/demo/turbo-status/');
      setStatus(res.data);
      if (res.data && !res.data.running && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    } catch {
      // server unreachable — buttons still work once it's up
    }
  };

  const startPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(pollStatus, 1000);
  };

  useEffect(() => {
    pollStatus();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post('/demo/turbo-start/', {
        readings: count,
        interval: speed,
      });
      setStatus(res.data.replay);
      startPolling();
    } catch (e) {
      setError(e.response?.data?.message || 'Failed to start turbo demo.');
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      await api.post('/demo/turbo-stop/');
      await pollStatus();
    } finally {
      setBusy(false);
    }
  };

  const running = Boolean(status?.running);
  const total = status?.total || 0;
  const current = status?.reading_number || 0;
  const percent = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;
  const remaining = (total - current) * (status?.interval_seconds || speed);

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 260 }}>
          <div className="stat-label">Turbo demo (100 readings in ~100 seconds)</div>
          <div style={{ fontSize: 13, color: '#5C6E71', marginTop: 2 }}>
            Fast dataset replay for presentations — RF + LSTM + 3-tier alerts fire in real
            time over WebSocket. Real data, not random.
          </div>

          <div style={{ display: 'flex', gap: 20, marginTop: 10, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 12, color: '#5C6E71', marginBottom: 4 }}>Speed</div>
              <div style={{ display: 'flex', gap: 6 }}>
                {SPEED_OPTIONS.map((o) => (
                  <button
                    key={o.value}
                    disabled={running}
                    onClick={() => setSpeed(o.value)}
                    style={{
                      padding: '4px 10px',
                      fontSize: 12,
                      background: speed === o.value ? '#2FA8A0' : '#E3E9EC',
                      color: speed === o.value ? '#fff' : '#37535B',
                      border: 'none',
                      borderRadius: 6,
                      cursor: running ? 'default' : 'pointer',
                    }}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div style={{ fontSize: 12, color: '#5C6E71', marginBottom: 4 }}>Readings</div>
              <div style={{ display: 'flex', gap: 6 }}>
                {COUNT_OPTIONS.map((n) => (
                  <button
                    key={n}
                    disabled={running}
                    onClick={() => setCount(n)}
                    style={{
                      padding: '4px 10px',
                      fontSize: 12,
                      background: count === n ? '#2FA8A0' : '#E3E9EC',
                      color: count === n ? '#fff' : '#37535B',
                      border: 'none',
                      borderRadius: 6,
                      cursor: running ? 'default' : 'pointer',
                    }}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {error && <div style={{ fontSize: 13, color: '#C1443C', marginTop: 6 }}>{error}</div>}

          {running && (
            <div style={{ marginTop: 8, fontSize: 13, color: '#5C6E71' }}>
              <span
                className="risk-badge high"
                style={{ display: 'inline-flex', marginRight: 8, verticalAlign: 'middle' }}
              >
                <span className="dot" />DEMO MODE
              </span>
              {status.current_patient != null && (
                <span>Dataset patient #{status.current_patient}</span>
              )}
              {status.target_patient != null && (
                <span style={{ marginLeft: 8 }}>
                  → writing to patient account #{status.target_patient}
                </span>
              )}
            </div>
          )}

          <div style={{ marginTop: 8, fontSize: 13, color: '#5C6E71' }}>
            {running
              ? `Reading ${current} of ${total} · ${percent}% · ~${fmt(remaining)} left`
              : status?.status === 'completed'
                ? `Completed — replayed ${total} readings.`
                : 'Not running.'}
          </div>

          <div
            className="progress-track"
            style={{
              height: 6,
              borderRadius: 3,
              background: '#E3E9EC',
              marginTop: 6,
              overflow: 'hidden',
            }}
          >
            <div
              className="progress-fill"
              style={{
                height: '100%',
                width: `${running ? percent : status?.status === 'completed' ? 100 : 0}%`,
                background: running ? '#2FA8A0' : '#B8C4C9',
                transition: 'width 0.3s ease',
              }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button disabled={busy || running} onClick={start}>
            {running ? 'Running…' : 'Start turbo demo'}
          </button>
          <button
            disabled={busy || !running}
            onClick={stop}
            style={{ background: running ? '#C1443C' : undefined }}
          >
            Stop
          </button>
        </div>
      </div>
    </div>
  );
}