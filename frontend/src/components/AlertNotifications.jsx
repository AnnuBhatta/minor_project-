import React, { useState, useEffect, useRef } from 'react';

const AlertNotifications = ({ userId }) => {
  const [alerts, setAlerts] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showAlerts, setShowAlerts] = useState(true);
  const wsRef = useRef(null);
  const audioRef = useRef(null);

  useEffect(() => {
    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }

    // Connect WebSocket
    connectWebSocket();

    // Fetch initial alerts
    fetchAlertHistory();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [userId]);

  const connectWebSocket = () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      console.log('No token found, skipping WebSocket connection');
      return;
    }

    try {
      const ws = new WebSocket(`ws://localhost:8000/ws/alerts/?token=${encodeURIComponent(token)}`);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('🔔 Alert WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('📨 Alert received:', data);
          
          if (data.type === 'new_alert' || data.type === 'alert_message') {
            const alert = data.alert || data.message;
            addAlert(alert);
            
            // Play sound for emergencies
            if (alert.severity === 'critical' || alert.severity === 'high') {
              playEmergencySound();
            }
            
            // Show browser notification
            showBrowserNotification(alert);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('Alert WebSocket error:', error);
      };

      ws.onclose = () => {
        console.log('Alert WebSocket disconnected');
        // Attempt to reconnect after 5 seconds
        setTimeout(connectWebSocket, 5000);
      };
    } catch (error) {
      console.error('WebSocket connection error:', error);
    }
  };

  const fetchAlertHistory = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) return;

      const response = await fetch('/api/ml/demo/history/', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        if (data.alerts) {
          setAlerts(data.alerts);
          const unread = data.alerts.filter(a => a.status === 'pending').length;
          setUnreadCount(unread);
        }
      }
    } catch (error) {
      console.error('Error fetching alert history:', error);
    }
  };

  const addAlert = (alert) => {
    setAlerts(prev => {
      // Check if alert already exists
      const exists = prev.some(a => a.id === alert.id);
      if (exists) return prev;
      
      const newAlerts = [alert, ...prev].slice(0, 50);
      return newAlerts;
    });
    setUnreadCount(prev => prev + 1);
  };

  const playEmergencySound = () => {
    if (audioRef.current) {
      audioRef.current.play().catch(error => {
        console.log('Audio play failed:', error);
      });
    } else {
      // Create a simple beep using Web Audio API
      try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        oscillator.frequency.value = 800;
        oscillator.type = 'square';
        
        gainNode.gain.setValueAtTime(0.3, audioCtx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
        
        oscillator.start(audioCtx.currentTime);
        oscillator.stop(audioCtx.currentTime + 0.3);
      } catch (error) {
        console.log('Could not play sound:', error);
      }
    }
  };

  const showBrowserNotification = (alert) => {
    if ('Notification' in window && Notification.permission === 'granted') {
      const tierEmoji = alert.tier === 1 ? '🚨' : alert.tier === 2 ? '⚠️' : '📉';
      new Notification(`${tierEmoji} ${alert.title}`, {
        body: alert.message?.substring(0, 100) || 'Health alert detected',
        icon: '/emergency-icon.png',
        tag: `alert-${alert.id}`,
        requireInteraction: alert.tier === 1 || alert.tier === 2,
        silent: false
      });
    }
  };

  const acknowledgeAlert = async (alertId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/alerts/${alertId}/acknowledge/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ status: 'acknowledged' })
      });
      
      if (response.ok) {
        setAlerts(prev => prev.map(a => 
          a.id === alertId ? { ...a, status: 'acknowledged' } : a
        ));
        setUnreadCount(prev => Math.max(0, prev - 1));
      }
    } catch (error) {
      console.error('Error acknowledging alert:', error);
    }
  };

  const resolveAlert = async (alertId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/alerts/${alertId}/resolve/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ status: 'resolved' })
      });
      
      if (response.ok) {
        setAlerts(prev => prev.map(a => 
          a.id === alertId ? { ...a, status: 'resolved' } : a
        ));
        setUnreadCount(prev => Math.max(0, prev - 1));
      }
    } catch (error) {
      console.error('Error resolving alert:', error);
    }
  };

  const getTierInfo = (alert) => {
    const tier = alert.tier || 2;
    const tiers = {
      1: {
        label: '🚨 EMERGENCY',
        color: '#f44336',
        bgColor: '#ffebee',
        borderColor: '#f44336',
        priority: 'Highest'
      },
      2: {
        label: '⚠️ HEALTH ALERT',
        color: '#ff9800',
        bgColor: '#fff3e0',
        borderColor: '#ff9800',
        priority: 'High'
      },
      3: {
        label: '📉 TREND ALERT',
        color: '#2196f3',
        bgColor: '#e3f2fd',
        borderColor: '#2196f3',
        priority: 'Medium'
      }
    };
    return tiers[tier] || tiers[2];
  };

  const getSeverityColor = (severity) => {
    switch(severity?.toLowerCase()) {
      case 'critical': return '#f44336';
      case 'high': return '#ff9800';
      case 'medium': return '#ffc107';
      case 'low': return '#4caf50';
      default: return '#2196f3';
    }
  };

  const clearAllAlerts = () => {
    if (window.confirm('Clear all alerts?')) {
      setAlerts([]);
      setUnreadCount(0);
    }
  };

  return (
    <div className="alerts-container">
      {/* Audio for emergency alerts */}
      <audio ref={audioRef} src="/emergency-alert.mp3" preload="auto" />
      
      <div className="alerts-header">
        <div className="alerts-title">
          <h2>🔔 Alerts</h2>
          {unreadCount > 0 && (
            <span className="unread-badge">{unreadCount}</span>
          )}
        </div>
        <div className="alerts-actions">
          <button 
            className="toggle-btn"
            onClick={() => setShowAlerts(!showAlerts)}
          >
            {showAlerts ? '📥 Hide' : '📤 Show'}
          </button>
          <button 
            className="clear-btn"
            onClick={clearAllAlerts}
            disabled={alerts.length === 0}
          >
            🗑️ Clear
          </button>
        </div>
      </div>

      {showAlerts && (
        <div className="alerts-list">
          {alerts.length === 0 ? (
            <div className="no-alerts">
              <span className="no-alerts-icon">✅</span>
              <p>No alerts</p>
              <span className="no-alerts-sub">All clear! You're healthy.</span>
            </div>
          ) : (
            alerts.map(alert => {
              const tierInfo = getTierInfo(alert);
              const severityColor = getSeverityColor(alert.severity);
              
              return (
                <div 
                  key={alert.id} 
                  className={`alert-item ${alert.status} tier-${alert.tier || 2}`}
                  style={{ 
                    borderLeftColor: tierInfo.borderColor || severityColor,
                    background: alert.status === 'pending' ? tierInfo.bgColor : '#f5f5f5'
                  }}
                >
                  <div className="alert-header">
                    <div className="alert-left">
                      <span className="alert-tier" style={{ color: tierInfo.color }}>
                        {tierInfo.label}
                      </span>
                      {alert.status === 'pending' && (
                        <span className="status-badge pending">NEW</span>
                      )}
                      {alert.status === 'acknowledged' && (
                        <span className="status-badge acknowledged">✓</span>
                      )}
                      {alert.status === 'resolved' && (
                        <span className="status-badge resolved">✓✓</span>
                      )}
                    </div>
                    <span className="alert-time">
                      {new Date(alert.created_at).toLocaleString()}
                    </span>
                  </div>
                  
                  <h4 className="alert-title">{alert.title}</h4>
                  <p className="alert-message">{alert.message}</p>
                  
                  <div className="alert-footer">
                    <div className="alert-meta">
                      <span className="severity-badge" style={{ 
                        background: severityColor,
                        color: 'white'
                      }}>
                        {alert.severity || 'Medium'}
                      </span>
                      {alert.tier && (
                        <span className="tier-badge">
                          Tier {alert.tier}
                        </span>
                      )}
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
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      <style>{`
        .alerts-container {
          width: 100%;
          max-width: 900px;
          margin: 0 auto;
          padding: 20px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          background: #f8f9fa;
          border-radius: 12px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .alerts-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
          padding-bottom: 10px;
          border-bottom: 2px solid #e0e0e0;
        }

        .alerts-title {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .alerts-title h2 {
          margin: 0;
          font-size: 24px;
          color: #333;
        }

        .unread-badge {
          background: #f44336;
          color: white;
          padding: 2px 10px;
          border-radius: 12px;
          font-size: 14px;
          font-weight: bold;
          animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
          0% { transform: scale(1); }
          50% { transform: scale(1.05); }
          100% { transform: scale(1); }
        }

        .alerts-actions {
          display: flex;
          gap: 8px;
        }

        .toggle-btn, .clear-btn {
          padding: 6px 14px;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          font-size: 14px;
          transition: all 0.2s;
        }

        .toggle-btn {
          background: #e0e0e0;
          color: #333;
        }

        .toggle-btn:hover {
          background: #d0d0d0;
        }

        .clear-btn {
          background: #ffebee;
          color: #c62828;
        }

        .clear-btn:hover:not(:disabled) {
          background: #ffcdd2;
        }

        .clear-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .alerts-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
          max-height: 600px;
          overflow-y: auto;
          padding-right: 5px;
        }

        .alerts-list::-webkit-scrollbar {
          width: 6px;
        }

        .alerts-list::-webkit-scrollbar-track {
          background: #f1f1f1;
          border-radius: 3px;
        }

        .alerts-list::-webkit-scrollbar-thumb {
          background: #c1c1c1;
          border-radius: 3px;
        }

        .alert-item {
          background: white;
          border-left: 4px solid #2196f3;
          padding: 16px;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.08);
          transition: all 0.3s ease;
          animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
          from {
            transform: translateX(-20px);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }

        .alert-item:hover {
          transform: translateX(5px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        }

        .alert-item.acknowledged {
          opacity: 0.7;
        }

        .alert-item.resolved {
          opacity: 0.5;
        }

        .alert-item.tier-1 {
          border-left-width: 6px;
        }

        .alert-item.tier-2 {
          border-left-width: 5px;
        }

        .alert-item.tier-3 {
          border-left-width: 4px;
        }

        .alert-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
          flex-wrap: wrap;
          gap: 8px;
        }

        .alert-left {
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
        }

        .alert-tier {
          font-weight: bold;
          font-size: 14px;
        }

        .status-badge {
          font-size: 11px;
          padding: 2px 8px;
          border-radius: 10px;
          font-weight: bold;
        }

        .status-badge.pending {
          background: #ff9800;
          color: white;
        }

        .status-badge.acknowledged {
          background: #2196f3;
          color: white;
        }

        .status-badge.resolved {
          background: #4caf50;
          color: white;
        }

        .alert-time {
          font-size: 12px;
          color: #999;
        }

        .alert-title {
          margin: 0 0 6px 0;
          font-size: 16px;
          color: #333;
        }

        .alert-message {
          margin: 0 0 12px 0;
          color: #666;
          font-size: 14px;
          line-height: 1.5;
        }

        .alert-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 8px;
          padding-top: 8px;
          border-top: 1px solid #f0f0f0;
        }

        .alert-meta {
          display: flex;
          gap: 8px;
          align-items: center;
        }

        .severity-badge {
          font-size: 11px;
          padding: 2px 12px;
          border-radius: 10px;
          font-weight: bold;
          text-transform: uppercase;
        }

        .tier-badge {
          font-size: 11px;
          padding: 2px 10px;
          border-radius: 10px;
          background: #e0e0e0;
          color: #666;
          font-weight: bold;
        }

        .alert-actions {
          display: flex;
          gap: 6px;
        }

        .acknowledge-btn, .resolve-btn {
          padding: 4px 12px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
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

        .no-alerts {
          text-align: center;
          padding: 40px 20px;
          background: white;
          border-radius: 8px;
          color: #666;
        }

        .no-alerts-icon {
          font-size: 48px;
          display: block;
          margin-bottom: 10px;
        }

        .no-alerts p {
          margin: 0;
          font-size: 18px;
          font-weight: 500;
        }

        .no-alerts-sub {
          font-size: 14px;
          color: #999;
        }

        /* Responsive */
        @media (max-width: 768px) {
          .alerts-container {
            padding: 12px;
          }

          .alerts-header {
            flex-direction: column;
            align-items: stretch;
            gap: 10px;
          }

          .alerts-actions {
            justify-content: flex-end;
          }

          .alert-header {
            flex-direction: column;
            align-items: flex-start;
          }

          .alert-footer {
            flex-direction: column;
            align-items: stretch;
          }

          .alert-actions {
            justify-content: flex-end;
          }

          .alerts-list {
            max-height: 400px;
          }
        }
      `}</style>
    </div>
  );
};

export default AlertNotifications;