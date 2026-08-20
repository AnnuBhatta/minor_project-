import React, { useState, useEffect, useRef, useCallback } from 'react';
import api from '../api';
import { useAlertsSocket } from '../contexts/WebSocketContext';
import LivePatientMap from './LivePatientMap';

const LiveAlertsPanel = () => {
  const { status: wsStatus, subscribe } = useAlertsSocket();

  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [loading, setLoading] = useState(true);
  const [alerts, setAlerts] = useState([]);
  const [liveLocations, setLiveLocations] = useState({}); // user_id -> {lat, lng}

  // Separate WebSocket for live emergency-location broadcasts.
  const locWsRef = useRef(null);

  const playSound = useCallback(() => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 880;
      osc.type = 'square';
      gain.gain.setValueAtTime(0.25, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.4);
    } catch (e) {
      console.log('Could not play sound:', e);
    }
  }, []);

  useEffect(() => {
    fetchPatients();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Live emergency-location channel, same origin as the page so it works in
  // dev (Vite proxies /ws) and in production (reverse proxy terminates TLS).
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    const wsProto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsBase = `${wsProto}://${window.location.host}`;
    const ws = new WebSocket(
      `${wsBase}/ws/location/?token=${encodeURIComponent(token)}`
    );
    locWsRef.current = ws;
    ws.onopen = () => console.log('[LOC] Connected to /ws/location/');
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'emergency_location' && data.location) {
          const loc = data.location;
          const uid = loc.user_id;
          setLiveLocations((prev) => ({
            ...prev,
            [uid]: {
              lat: loc.latitude ?? loc.lat,
              lng: loc.longitude ?? loc.lng,
              timestamp: loc.timestamp,
            },
          }));
          console.log('[LOC] Emergency location received:', loc);
        }
      } catch (e) {
        console.error('[LOC] Bad message:', e);
      }
    };
    ws.onclose = () => console.warn('[LOC] Disconnected');
    return () => {
      if (ws) ws.close();
    };
  }, []);

  const fetchPatients = async () => {
    try {
      const { data } = await api.get('/auth/my-patients/');
      const list = Array.isArray(data) ? data : data.patients || [];
      setPatients(list);
      if (list.length > 0) setSelectedPatient(list[0]);
      fetchAlerts();
    } catch (error) {
      console.error('Error fetching patients:', error);
      setLoading(false);
    }
  };

  // For a guardian, /alerts/ returns alerts for all linked patients.
  const fetchAlerts = async () => {
    try {
      const { data } = await api.get('/alerts/');
      const list = Array.isArray(data) ? data : data.results || [];
      setAlerts(list);
    } catch (error) {
      console.error('Error fetching alerts:', error);
    } finally {
      setLoading(false);
    }
  };

  // Real-time alerts pushed by the backend over /ws/alerts/.
  useEffect(() => {
    return subscribe((alert) => {
      console.log('👁 Guardian received live alert:', alert);
      setAlerts((prev) => {
        if (prev.some((a) => a.id === alert.id)) return prev;
        return [alert, ...prev];
      });
      if (alert.severity === 'critical' || alert.severity === 'high') {
        playSound();
      }
    });
  }, [subscribe, playSound]);

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical': return '#f44336';
      case 'high': return '#ff9800';
      case 'medium': return '#ffc107';
      case 'low': return '#4caf50';
      default: return '#2196f3';
    }
  };

  const visibleAlerts = selectedPatient
    ? alerts.filter((a) => !a.user_id || a.user_id === selectedPatient.id)
    : alerts;

  const liveLoc = selectedPatient ? liveLocations[selectedPatient.id] : null;

  return (
    <div className="live-alerts-panel">
      <div className="panel-header">
        <h3 style={{ margin: 0 }}>🔔 Real-time Alerts</h3>
        <span
          className={`ws-pill ${wsStatus === 'open' ? 'online' : 'offline'}`}
          title="Alert WebSocket status"
        >
          {wsStatus === 'open' ? '● Live' : `○ ${wsStatus}`}
        </span>
      </div>

      {patients.length > 0 && (
        <div className="patient-pills">
          {patients.map((p) => (
            <button
              key={p.id}
              className={`patient-pill ${selectedPatient?.id === p.id ? 'active' : ''}`}
              onClick={() => setSelectedPatient(p)}
            >
              {p.full_name || p.username}
            </button>
          ))}
        </div>
      )}

      {liveLoc && (
        <div className="live-location">
          <strong>🚨 Live emergency location: </strong>
          <a
            href={`https://www.google.com/maps?q=${liveLoc.lat},${liveLoc.lng}`}
            target="_blank"
            rel="noreferrer"
          >
            {liveLoc.lat.toFixed(5)}, {liveLoc.lng.toFixed(5)}
          </a>
        </div>
      )}

      {loading ? (
        <div className="loading">Loading alerts...</div>
      ) : visibleAlerts.length === 0 ? (
        <div className="no-alerts">✅ No alerts - All clear!</div>
      ) : (
        <div className="alerts-list">
          {visibleAlerts.map((alert) => (
            <div
              key={alert.id}
              className={`alert-card ${alert.severity}`}
              style={{ borderLeftColor: getSeverityColor(alert.severity) }}
            >
              <div className="alert-header">
                <span className="alert-title">
                  {alert.tier === 1 ? '🚨 ' : alert.tier === 2 ? '⚠️ ' : alert.tier === 3 ? '📉 ' : ''}
                  {alert.title}
                </span>
                <span className="alert-time">
                  {new Date(alert.created_at).toLocaleString()}
                </span>
              </div>
              {alert.tier && (
                <span className={`tier-badge tier-${alert.tier}`}>
                  {alert.tier === 1 ? 'EMERGENCY' : alert.tier === 2 ? 'HEALTH ALERT' : 'TREND ALERT'}
                </span>
              )}
              <p className="alert-message"><strong>Reason:</strong> {alert.message}</p>
              <div className="alert-footer">
                <span className={`alert-status ${alert.status}`}>
                  {alert.status}
                </span>
                {alert.location && (
                  <button
                    className="location-btn"
                    onClick={() => {
                      window.open(
                        `https://www.google.com/maps?q=${alert.location.lat},${alert.location.lng}`,
                        '_blank'
                      );
                    }}
                  >
                    📍 View Location
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <LivePatientMap patientId={selectedPatient?.id} patientName={selectedPatient?.full_name} />

      <style>{`
        .live-alerts-panel {
          background: white;
          padding: 20px;
          border-radius: 12px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.08);
          margin-top: 16px;
        }

        .panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }

        .ws-pill {
          padding: 4px 12px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: bold;
          background: #eceff1;
        }

        .ws-pill.online { color: #2e7d32; background: #e8f5e9; }
        .ws-pill.offline { color: #c62828; background: #ffebee; }

        .patient-pills {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 14px;
        }

        .patient-pill {
          padding: 6px 14px;
          border: 1px solid #cfd8dc;
          border-radius: 16px;
          background: #fff;
          cursor: pointer;
          font-size: 13px;
          color: #37474f;
        }

        .patient-pill.active {
          background: #1976d2;
          color: white;
          border-color: #1976d2;
        }

        .live-location {
          padding: 10px 14px;
          background: #ffebee;
          border-radius: 8px;
          margin-bottom: 12px;
          font-size: 13px;
          color: #b71c1c;
        }

        .alerts-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
          max-height: 500px;
          overflow-y: auto;
        }

        .alert-card {
          padding: 15px;
          border-left: 4px solid #2196f3;
          border-radius: 4px;
          background: #fafafa;
          transition: all 0.3s;
        }

        .alert-card:hover {
          transform: translateX(5px);
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .alert-card.critical { background: #ffebee; }
        .alert-card.high { background: #fff3e0; }

        .alert-header {
          display: flex;
          justify-content: space-between;
          margin-bottom: 8px;
          flex-wrap: wrap;
          gap: 5px;
        }

        .alert-title { font-weight: bold; color: #333; }
        .alert-time { font-size: 12px; color: #999; }

        .alert-message {
          margin: 0 0 10px 0;
          color: #666;
          font-size: 14px;
        }

        .tier-badge {
          display: inline-block;
          padding: 2px 10px;
          border-radius: 10px;
          font-size: 11px;
          font-weight: bold;
          color: white;
          margin-bottom: 8px;
        }

        .tier-badge.tier-1 { background: #f44336; }
        .tier-badge.tier-2 { background: #ff9800; }
        .tier-badge.tier-3 { background: #8a6d3b; }

        .alert-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
        }

        .alert-status {
          font-size: 12px;
          font-weight: bold;
          text-transform: uppercase;
        }

        .alert-status.pending { color: #ff9800; }
        .alert-status.acknowledged { color: #2196f3; }
        .alert-status.resolved { color: #4caf50; }

        .location-btn {
          padding: 4px 12px;
          background: #1976d2;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
        }

        .location-btn:hover { background: #1565c0; }

        .no-alerts {
          text-align: center;
          padding: 40px;
          color: #666;
          font-size: 16px;
        }

        .loading {
          text-align: center;
          padding: 40px;
          color: #666;
        }
      `}</style>
    </div>
  );
};

export default LiveAlertsPanel;