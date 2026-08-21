import React, { useState, useEffect, useRef, useCallback } from 'react';
import api from '../api';
import { useAlertsSocket } from '../contexts/WebSocketContext';
import LivePatientMap from './LivePatientMap';

const GuardianDashboard = () => {
  const { status: wsStatus, subscribe } = useAlertsSocket();

  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [loading, setLoading] = useState(true);
  const [alerts, setAlerts] = useState([]);
  const [liveLocations, setLiveLocations] = useState({});
  const [showAlerts, setShowAlerts] = useState(true);

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
  }, []);

  // ✅ UPDATED: WebSocket for emergency alerts with location
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    
    const wsProto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsBase = `${wsProto}://${window.location.host}`;
    const ws = new WebSocket(`${wsBase}/ws/emergency/?token=${encodeURIComponent(token)}`);
    locWsRef.current = ws;
    
    ws.onopen = () => console.log('[EMERGENCY] Connected to /ws/emergency/');
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[EMERGENCY] Received:', data);
        
        // Handle emergency alert with location
        if (data.type === 'emergency_alert' && data.data) {
          const alertData = data.data;
          console.log('[EMERGENCY] Alert data:', alertData);
          
          // Update location if present
          if (alertData.location) {
            const loc = alertData.location;
            setLiveLocations((prev) => ({
              ...prev,
              [alertData.user_id]: {
                lat: loc.lat || loc.latitude || 0,
                lng: loc.lng || loc.longitude || 0,
                timestamp: alertData.timestamp || new Date().toISOString()
              }
            }));
            console.log('[EMERGENCY] Location updated:', loc);
          }
          
          // Add to alerts list
          setAlerts((prev) => {
            if (prev.some(a => a.id === alertData.id)) return prev;
            return [{
              id: alertData.id,
              title: alertData.title || '🚨 EMERGENCY ALERT',
              message: alertData.message || 'Emergency alert received',
              severity: alertData.severity || 'critical',
              status: alertData.status || 'pending',
              location: alertData.location,
              user_id: alertData.user_id,
              user_name: alertData.user_name,
              created_at: alertData.timestamp || new Date().toISOString(),
              tier: 1
            }, ...prev];
          });
          
          // Play sound
          playSound();
        }
        
        // Handle emergency location separately
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
          console.log('[EMERGENCY] Emergency location received:', loc);
        }
      } catch (e) {
        console.error('[EMERGENCY] Bad message:', e);
      }
    };
    
    ws.onclose = () => console.warn('[EMERGENCY] Disconnected');
    ws.onerror = (e) => console.error('[EMERGENCY] Error:', e);
    
    return () => {
      if (ws) ws.close();
    };
  }, [playSound]);

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

  // Real-time alerts pushed by the backend over /ws/alerts/
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

  const acknowledgeAlert = async (alertId) => {
    try {
      await api.patch(`/alerts/${alertId}/acknowledge/`, { status: 'acknowledged' });
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === alertId ? { ...a, status: 'acknowledged' } : a
        )
      );
    } catch (error) {
      console.error('Error acknowledging alert:', error);
    }
  };

  const resolveAlert = async (alertId) => {
    try {
      await api.patch(`/alerts/${alertId}/acknowledge/`, { status: 'resolved' });
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === alertId ? { ...a, status: 'resolved' } : a
        )
      );
    } catch (error) {
      console.error('Error resolving alert:', error);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    window.location.href = '/login';
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical': return '#f44336';
      case 'high': return '#ff9800';
      case 'medium': return '#ffc107';
      case 'low': return '#4caf50';
      default: return '#2196f3';
    }
  };

  const getTierLabel = (tier) => {
    switch (tier) {
      case 1: return { label: '🚨 EMERGENCY', color: '#f44336' };
      case 2: return { label: '⚠️ HEALTH ALERT', color: '#ff9800' };
      case 3: return { label: '📉 TREND ALERT', color: '#8a6d3b' };
      default: return { label: '🔔 ALERT', color: '#2196f3' };
    }
  };

  const visibleAlerts = selectedPatient
    ? alerts.filter((a) => !a.user_id || a.user_id === selectedPatient.id)
    : alerts;

  const liveLoc = selectedPatient ? liveLocations[selectedPatient.id] : null;

  const user = React.useMemo(() => {
    try {
      const userData = localStorage.getItem('user');
      return userData ? JSON.parse(userData) : null;
    } catch {
      return null;
    }
  }, []);

  return (
    <div className="guardian-dashboard">
      <header className="dashboard-header">
        <h1>📱 Guardian Dashboard</h1>
        <div className="user-info">
          <span>Welcome, {user?.first_name || 'Guardian'}!</span>
          <button onClick={handleLogout} className="logout-btn">Logout</button>
        </div>
      </header>

      <div className="dashboard-content">
        <div className="patients-section">
          <h2>👤 My Patients</h2>
          {patients.length === 0 ? (
            <div className="no-patients">
              <p>No patients assigned yet.</p>
              <p className="hint">When a patient adds you as a guardian, they will appear here.</p>
            </div>
          ) : (
            <div className="patient-list">
              {patients.map((patient) => (
                <div
                  key={patient.id}
                  className={`patient-card ${selectedPatient?.id === patient.id ? 'active' : ''}`}
                  onClick={() => setSelectedPatient(patient)}
                >
                  <div className="patient-avatar">
                    {patient.first_name?.[0] || patient.username?.[0] || 'P'}
                  </div>
                  <div className="patient-info">
                    <h4>{patient.full_name || patient.username}</h4>
                    <p>{patient.email}</p>
                    <span className={`status ${patient.is_online ? 'online' : 'offline'}`}>
                      {patient.is_online ? '● Online' : '○ Offline'}
                    </span>
                  </div>
                  {liveLocations[patient.id] && (
                    <span className="live-badge">📍 LIVE</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="alerts-section">
          <div className="alerts-header">
            <h2>🔔 Alerts</h2>
            <div className="alerts-controls">
              <span
                className={`ws-pill ${wsStatus === 'open' ? 'online' : 'offline'}`}
                title="Alert WebSocket status"
              >
                {wsStatus === 'open' ? '● Live' : `○ ${wsStatus}`}
              </span>
              <button 
                className="toggle-btn"
                onClick={() => setShowAlerts(!showAlerts)}
              >
                {showAlerts ? '📥 Hide' : '📤 Show'}
              </button>
            </div>
          </div>

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

          {showAlerts && (
            <>
              {loading ? (
                <div className="loading">Loading alerts...</div>
              ) : visibleAlerts.length === 0 ? (
                <div className="no-alerts">✅ No alerts - All clear!</div>
              ) : (
                <div className="alerts-list">
                  {visibleAlerts.map((alert) => {
                    const tierInfo = getTierLabel(alert.tier);
                    return (
                      <div
                        key={alert.id}
                        className={`alert-card ${alert.severity}`}
                        style={{ borderLeftColor: getSeverityColor(alert.severity) }}
                      >
                        <div className="alert-header">
                          <span className="alert-title" style={{ color: tierInfo.color }}>
                            {tierInfo.label}
                          </span>
                          <span className="alert-time">
                            {new Date(alert.created_at).toLocaleString()}
                          </span>
                        </div>
                        <h4 className="alert-headline">{alert.title}</h4>
                        <p className="alert-message">
                          <strong>Reason:</strong> {alert.message}
                        </p>
                        {alert.location && (
                          <p className="alert-location">
                            <strong>📍 Location:</strong> {alert.location.lat}, {alert.location.lng}
                          </p>
                        )}
                        <div className="alert-footer">
                          <div className="alert-meta">
                            <span className={`alert-status ${alert.status}`}>
                              {alert.status}
                            </span>
                            <span className="severity-badge" style={{ 
                              background: getSeverityColor(alert.severity),
                              color: 'white'
                            }}>
                              {alert.severity || 'Medium'}
                            </span>
                          </div>
                          <div className="alert-actions">
                            {alert.status === 'pending' && (
                              <>
                                <button 
                                  className="acknowledge-btn"
                                  onClick={() => acknowledgeAlert(alert.id)}
                                >
                                  ✅ Acknowledge
                                </button>
                                <button 
                                  className="resolve-btn"
                                  onClick={() => resolveAlert(alert.id)}
                                >
                                  ✅ Resolve
                                </button>
                              </>
                            )}
                            {alert.status === 'acknowledged' && (
                              <button 
                                className="resolve-btn"
                                onClick={() => resolveAlert(alert.id)}
                              >
                                ✅ Resolve
                              </button>
                            )}
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
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <div className="map-section">
        <LivePatientMap 
          patientId={selectedPatient?.id} 
          patientName={selectedPatient?.full_name} 
        />
      </div>

      <style>{`
        .guardian-dashboard {
          max-width: 1200px;
          margin: 0 auto;
          padding: 20px;
          font-family: Arial, sans-serif;
          background: #f5f7fa;
          min-height: 100vh;
        }

        .dashboard-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px 30px;
          background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%);
          color: white;
          border-radius: 12px;
          margin-bottom: 30px;
          flex-wrap: wrap;
          gap: 10px;
        }

        .dashboard-header h1 {
          margin: 0;
          font-size: 24px;
        }

        .user-info {
          display: flex;
          align-items: center;
          gap: 15px;
        }

        .logout-btn {
          padding: 8px 20px;
          background: rgba(255,255,255,0.15);
          border: 1px solid rgba(255,255,255,0.3);
          border-radius: 6px;
          color: white;
          cursor: pointer;
          transition: all 0.3s;
        }

        .logout-btn:hover {
          background: rgba(255,255,255,0.25);
        }

        .dashboard-content {
          display: grid;
          grid-template-columns: 300px 1fr;
          gap: 30px;
        }

        .patients-section {
          background: white;
          padding: 20px;
          border-radius: 12px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        .patients-section h2 {
          margin-top: 0;
          color: #333;
          font-size: 18px;
        }

        .patient-list {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .patient-card {
          display: flex;
          align-items: center;
          gap: 15px;
          padding: 12px;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.3s;
          border: 2px solid transparent;
          position: relative;
        }

        .patient-card:hover {
          background: #f5f5f5;
        }

        .patient-card.active {
          border-color: #1976d2;
          background: #e3f2fd;
        }

        .patient-avatar {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          background: #1976d2;
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: bold;
          font-size: 18px;
          flex-shrink: 0;
        }

        .patient-info {
          flex: 1;
        }

        .patient-info h4 {
          margin: 0;
          font-size: 14px;
          color: #333;
        }

        .patient-info p {
          margin: 2px 0;
          font-size: 12px;
          color: #666;
        }

        .status {
          font-size: 12px;
          font-weight: bold;
        }

        .status.online {
          color: #4caf50;
        }

        .status.offline {
          color: #999;
        }

        .live-badge {
          background: #f44336;
          color: white;
          padding: 2px 8px;
          border-radius: 10px;
          font-size: 10px;
          font-weight: bold;
          animation: pulse 1.5s infinite;
        }

        .no-patients {
          text-align: center;
          padding: 20px;
          color: #666;
        }

        .hint {
          font-size: 12px;
          color: #999;
        }

        .alerts-section {
          background: white;
          padding: 20px;
          border-radius: 12px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        .alerts-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
          flex-wrap: wrap;
          gap: 10px;
        }

        .alerts-header h2 {
          margin: 0;
          color: #333;
          font-size: 18px;
        }

        .alerts-controls {
          display: flex;
          gap: 10px;
          align-items: center;
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

        .toggle-btn {
          padding: 4px 12px;
          border: 1px solid #ddd;
          border-radius: 6px;
          background: white;
          cursor: pointer;
          font-size: 12px;
        }

        .toggle-btn:hover {
          background: #f5f5f5;
        }

        .live-location {
          padding: 10px 14px;
          background: #ffebee;
          border-radius: 8px;
          margin-bottom: 12px;
          font-size: 13px;
          color: #b71c1c;
        }

        .live-location a {
          color: #1976d2;
          text-decoration: none;
          font-weight: bold;
        }

        .live-location a:hover {
          text-decoration: underline;
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

        .alert-title {
          font-weight: bold;
          font-size: 14px;
        }

        .alert-time {
          font-size: 12px;
          color: #999;
        }

        .alert-headline {
          margin: 0 0 6px 0;
          color: #333;
          font-size: 15px;
        }

        .alert-message {
          margin: 0 0 10px 0;
          color: #666;
          font-size: 14px;
        }

        .alert-location {
          font-size: 13px;
          color: #1976d2;
          margin: 0 0 10px 0;
        }

        .alert-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
        }

        .alert-meta {
          display: flex;
          gap: 8px;
          align-items: center;
        }

        .alert-status {
          font-size: 12px;
          font-weight: bold;
          text-transform: uppercase;
        }

        .alert-status.pending { color: #ff9800; }
        .alert-status.acknowledged { color: #2196f3; }
        .alert-status.resolved { color: #4caf50; }

        .severity-badge {
          font-size: 10px;
          padding: 2px 10px;
          border-radius: 10px;
          font-weight: bold;
          text-transform: uppercase;
        }

        .alert-actions {
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
        }

        .acknowledge-btn, .resolve-btn, .location-btn {
          padding: 4px 12px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 11px;
          font-weight: 500;
          transition: all 0.2s;
        }

        .acknowledge-btn {
          background: #2196f3;
          color: white;
        }

        .acknowledge-btn:hover {
          background: #1976d2;
        }

        .resolve-btn {
          background: #4caf50;
          color: white;
        }

        .resolve-btn:hover {
          background: #388e3c;
        }

        .location-btn {
          background: #1976d2;
          color: white;
        }

        .location-btn:hover {
          background: #1565c0;
        }

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

        .map-section {
          margin-top: 30px;
          background: white;
          border-radius: 12px;
          padding: 16px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        @keyframes pulse {
          0% { opacity: 1; }
          50% { opacity: 0.5; }
          100% { opacity: 1; }
        }

        @media (max-width: 768px) {
          .dashboard-content {
            grid-template-columns: 1fr;
          }

          .dashboard-header {
            flex-direction: column;
            text-align: center;
          }

          .user-info {
            flex-direction: column;
            width: 100%;
          }

          .logout-btn {
            width: 100%;
          }

          .alerts-header {
            flex-direction: column;
            align-items: stretch;
          }

          .alerts-controls {
            justify-content: space-between;
          }

          .alert-footer {
            flex-direction: column;
            align-items: stretch;
          }

          .alert-actions {
            justify-content: flex-start;
          }
        }
      `}</style>
    </div>
  );
};

export default GuardianDashboard;