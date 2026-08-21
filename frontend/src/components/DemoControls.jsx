import { useEffect, useRef, useState } from 'react';
import api from '../api';

/*
 * Dataset-replay demo controls.
 *
 * Replays the real training dataset (vital_signs_dataset.csv) through the
 * live ingest pipeline as simulated smartwatch data. Every reading runs the
 * RF + LSTM models and the three-tier alert system, so alerts reach the
 * guardian dashboard via WebSocket exactly like a real device would.
 *
 * Auto-starts once when the page mounts (idempotent) so data is always
 * flowing, and shows a DEMO MODE badge + live progress while running.
 */

export default function DemoControls({ onTick }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [genBusy, setGenBusy] = useState(false);
  const [genError, setGenError] = useState(null);
  const [genResult, setGenResult] = useState(null);
  const pollRef = useRef(null);

  const readReplay = (data) => (data && data.replay) || data || null;

  const pollStatus = async () => {
    try {
      const res = await api.get('/demo/status/');
      const replay = readReplay(res.data);
      setStatus(replay);
      if (onTick) onTick(replay);
      if (replay && !replay.running && pollRef.current) {
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
    let cancelled = false;
    const autoStart = async () => {
      try {
        const res = await api.get('/demo/status/');
        if (cancelled) return;
        if (res.data.replay?.running) {
          setStatus(res.data.replay);
        } else {
          await api.post('/demo/start/', { interval_seconds: 2, sample_readings: 100 });
          if (cancelled) return;
          setStatus({ running: true, status: 'running', total_readings: 100 });
        }
        startPolling();
      } catch {
        // backend not up yet
      }
    };
    autoStart();
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post('/demo/start/', { interval_seconds: 2, sample_readings: 100 });
      setStatus({ running: true, status: 'running', total_readings: 100 });
      startPolling();
    } catch (e) {
      setError(e.response?.data?.message || 'Failed to start demo replay.');
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      await api.post('/demo/stop/');
      await pollStatus();
    } finally {
      setBusy(false);
    }
  };

  const getPosition = () =>
    new Promise((resolve) => {
      if (!navigator.geolocation) return resolve(null);
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        }),
        () => resolve(null),
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });

  const runGuaranteed = async (endpoint, label) => {
    setGenBusy(true);
    setGenError(null);
    setGenResult(null);
    try {
      // Tier 3 / full demos replay ~63 readings through RF + LSTM, which
      // takes ~40s. The global axios timeout is 10s, so override it here.
      const location = await getPosition();
      const res = await api.post(
        `/demo/alert/${endpoint}/`,
        location ? { location } : {},
        { timeout: 300000 }
      );
      setGenResult({ ...res.data, _label: label });
    } catch (e) {
      setGenError(e.response?.data?.message || `Failed to run ${label}.`);
    } finally {
      setGenBusy(false);
    }
  };

  const tierBadge = (tier) => {
    const map = { 1: '🚨 Tier 1', 2: '⚠️ Tier 2', 3: '📉 Tier 3', all: '🎬 Full demo' };
    return map[tier] || `Tier ${tier}`;
  };

  const running = Boolean(status?.running);
  const total = status?.total_readings || 0;
  const current = status?.cycle_reading_index || 0;
  const percent = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div className="stat-label">Demo mode (dataset replay)</div>
          <div style={{ fontSize: 13, color: '#5C6E71', marginTop: 2 }}>
            Replays the real training dataset through the live ingest pipeline —
            RF + LSTM + 3-tier alerts fire like a real smartwatch.
          </div>

          {error && (
            <div style={{ fontSize: 13, color: '#C1443C', marginTop: 6 }}>{error}</div>
          )}

          {running && (
            <div style={{ marginTop: 8, fontSize: 13, color: '#5C6E71' }}>
              <span
                className="risk-badge high"
                style={{ display: 'inline-flex', marginRight: 8, verticalAlign: 'middle' }}
              >
                <span className="dot" />DEMO MODE
              </span>
              {status.cycle > 1 && <span>· cycle {status.cycle}</span>}
            </div>
          )}

          <div style={{ marginTop: 8, fontSize: 13, color: '#5C6E71' }}>
            {running
              ? `Reading ${current.toLocaleString()} of ${total.toLocaleString()} (${percent}%)`
              : 'Not running.'}
            {running && status.sample_readings > 0 && (
              <span style={{ marginLeft: 8 }}>
                · sampled {status.sample_readings.toLocaleString()} of{' '}
                {status.dataset_readings.toLocaleString()} real rows
              </span>
            )}
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
                width: `${running ? percent : 0}%`,
                background: running ? '#2FA8A0' : '#B8C4C9',
                transition: 'width 0.3s ease',
              }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            disabled={genBusy}
            onClick={() => runGuaranteed('tier1', 'Emergency')}
            style={{
              background: '#C1443C',
              padding: '10px 18px',
              fontSize: 14,
              fontWeight: 700,
              boxShadow: '0 2px 8px rgba(193,68,60,0.4)',
            }}
          >
            🚨 MANUAL EMERGENCY
          </button>
          <button disabled={busy || running} onClick={start}>
            {running ? 'Running…' : 'Start demo'}
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

      <div
        className="card"
        style={{
          marginTop: 14,
          borderLeft: '3px solid #C1443C',
          padding: '12px 14px',
        }}
      >
        <div className="stat-label">Guaranteed alerts (for presentations)</div>
        <div style={{ fontSize: 13, color: '#5C6E71', marginTop: 2 }}>
          Scripted vital patterns that deterministically fire each tier through the
          real RF + LSTM + 3-tier pipeline — WebSocket + email fire too.
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
          <button
            disabled={genBusy}
            onClick={() => runGuaranteed('tier1', 'Emergency')}
            style={{ background: '#C1443C' }}
          >
            🚨 Emergency (Tier 1)
          </button>
          <button
            disabled={genBusy}
            onClick={() => runGuaranteed('tier2', 'Health Alert')}
            style={{ background: '#D97A26' }}
          >
            ⚠️ Health Alert (Tier 2)
          </button>
          <button
            disabled={genBusy}
            onClick={() => runGuaranteed('tier3', 'Trend Alert')}
            style={{ background: '#8A6D3B' }}
          >
            📉 Trend Alert (Tier 3)
          </button>
          <button disabled={genBusy} onClick={() => runGuaranteed('full', 'Full demo')}>
            🎬 Full demo (1 + 2 + 3)
          </button>
        </div>

        {genError && (
          <div style={{ fontSize: 13, color: '#C1443C', marginTop: 8 }}>{genError}</div>
        )}

        {genResult && (
          <div style={{ marginTop: 10, fontSize: 13, color: '#5C6E71' }}>
            <div>
              <strong>{genResult.confirmed ? '✅ FIRED' : '❌ NOT FIRED'}</strong> —{' '}
              <span className="risk-badge high" style={{ display: 'inline-flex' }}>
                {tierBadge(genResult.tier)}
              </span>
              {genResult.tiers_triggered && (
                <span style={{ marginLeft: 8 }}>
                  tiers seen: [{genResult.tiers_triggered.join(', ')}]
                </span>
              )}
            </div>
            <div style={{ marginTop: 6 }}>{genResult.summary}</div>
            {genResult.reason && (
              <div style={{ marginTop: 6, color: '#37535B' }}>📋 Reason: {genResult.reason}</div>
            )}
            {genResult.alert?.message && (
              <div style={{ marginTop: 4 }}>💬 {genResult.alert.message}</div>
            )}
            {genResult.scenarios && (
              <div style={{ marginTop: 6 }}>
                {genResult.scenarios.map((s, i) => (
                  <div key={i} style={{ marginTop: 4 }}>
                    <strong>{tierBadge(s.tier)}</strong>{' '}
                    <span style={{ color: s.confirmed ? '#2F8F5B' : '#C1443C' }}>
                      {s.confirmed ? '✅' : '❌'}
                    </span>{' '}
                    — {s.summary}
                    {s.alert?.message && (
                      <div style={{ marginLeft: 18, color: '#37535B' }}>💬 {s.alert.message}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}