import React, { useState, useEffect } from 'react';
import LiveLocationTracker from './LiveLocationTracker';

const EmergencyDashboard = ({ emergencyEventId }) => {
  const [emergency, setEmergency] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    fetchEmergencyDetails();
  }, [emergencyEventId]);
  
  const fetchEmergencyDetails = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      
      if (!token) {
        setError('Please login first');
        setLoading(false);
        return;
      }
      
      const response = await fetch(`/api/emergency/events/${emergencyEventId}/`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setEmergency(data);
      } else if (response.status === 401) {
        setError('Please login again');
      } else {
        setError('Failed to fetch emergency details');
      }
    } catch (error) {
      console.error('Error fetching emergency:', error);
      setError('Network error');
    } finally {
      setLoading(false);
    }
  };
  
  const resolveEmergency = async () => {
    if (!window.confirm('Resolve this emergency?')) return;
    
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/emergency/events/${emergency.id}/resolve/`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        alert('Emergency resolved successfully!');
        window.location.reload();
      } else {
        alert('Failed to resolve emergency');
      }
    } catch (error) {
      console.error('Error resolving emergency:', error);
      alert('Failed to resolve emergency');
    }
  };
  
  if (loading) {
    return <div className="loading">Loading emergency details...</div>;
  }
  
  if (error) {
    return (
      <div className="error-container">
        <h2>⚠️ Error</h2>
        <p>{error}</p>
        <button onClick={() => window.location.href = '/live-status'}>Go to Dashboard</button>
      </div>
    );
  }
  
  if (!emergency) {
    return <div className="error">Emergency not found</div>;
  }
  
  return (
    <div className="emergency-dashboard">
      <div className="emergency-header">
        <h1 className="emergency-title">🚨 Emergency Tracking</h1>
        <div className="emergency-info">
          <div className={`severity-badge ${emergency.severity}`}>
            {emergency.severity?.toUpperCase() || 'UNKNOWN'}
          </div>
          <div className="status-badge">{emergency.status || 'ACTIVE'}</div>
          <div className="time">{emergency.created_at ? new Date(emergency.created_at).toLocaleString() : 'N/A'}</div>
        </div>
      </div>
      
      <div className="patient-info">
        <h3>Patient Information</h3>
        <div className="info-grid">
          <div><strong>Name:</strong> {emergency.user_details?.full_name || 'Unknown'}</div>
          <div><strong>Email:</strong> {emergency.user_details?.email || 'N/A'}</div>
          <div><strong>Phone:</strong> {emergency.user_details?.phone || 'N/A'}</div>
          <div><strong>Description:</strong> {emergency.description || 'No description'}</div>
        </div>
      </div>
      
      <div className="tracker-section">
        <LiveLocationTracker 
          userId={emergency.user}
          isEmergency={true}
          emergencyEventId={emergency.id}
          onLocationUpdate={(location) => {
            console.log('Location updated:', location);
          }}
        />
      </div>
      
      <div className="actions">
        <button 
          className="action-btn call-emergency"
          onClick={() => {
            if (window.confirm('Call emergency services?')) {
              window.location.href = `tel:911`;
            }
          }}
        >
          📞 Call Emergency Services
        </button>
        
        <button 
          className="action-btn directions"
          onClick={() => {
            const { lat = 0, lng = 0, latitude = lat, longitude = lng } = emergency.location || {};
            window.open(
              `https://www.google.com/maps/dir/?api=1&destination=${latitude},${longitude}`,
              '_blank'
            );
          }}
        >
          🗺️ Get Directions
        </button>
        
        <button 
          className="action-btn resolve"
          onClick={resolveEmergency}
        >
          ✅ Resolve Emergency
        </button>
      </div>

      <style>{`
        .emergency-dashboard {
          max-width: 1200px;
          margin: 0 auto;
          padding: 20px;
          font-family: Arial, sans-serif;
        }
        
        .emergency-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
          flex-wrap: wrap;
          gap: 10px;
        }
        
        .emergency-title {
          color: #f44336;
          margin: 0;
          font-size: 28px;
        }
        
        .emergency-info {
          display: flex;
          gap: 10px;
          align-items: center;
          flex-wrap: wrap;
        }
        
        .severity-badge {
          padding: 5px 10px;
          border-radius: 4px;
          color: white;
          font-weight: bold;
          text-transform: uppercase;
        }
        
        .severity-badge.critical {
          background: #f44336;
        }
        
        .severity-badge.high {
          background: #ff9800;
        }
        
        .severity-badge.medium {
          background: #ffc107;
        }
        
        .severity-badge.low {
          background: #4caf50;
        }
        
        .status-badge {
          padding: 5px 10px;
          border-radius: 4px;
          background: #2196f3;
          color: white;
          font-weight: bold;
          text-transform: uppercase;
        }
        
        .patient-info {
          background: #f5f5f5;
          padding: 20px;
          border-radius: 8px;
          margin-bottom: 20px;
        }
        
        .patient-info h3 {
          margin-top: 0;
          color: #333;
        }
        
        .info-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 10px;
        }
        
        .tracker-section {
          background: white;
          border-radius: 8px;
          overflow: hidden;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
          margin-bottom: 20px;
        }
        
        .actions {
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
        }
        
        .action-btn {
          padding: 12px 24px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-weight: bold;
          color: white;
          transition: opacity 0.3s;
          font-size: 16px;
        }
        
        .action-btn:hover {
          opacity: 0.9;
        }
        
        .action-btn.call-emergency {
          background: #f44336;
        }
        
        .action-btn.directions {
          background: #4caf50;
        }
        
        .action-btn.resolve {
          background: #2196f3;
        }
        
        .loading {
          text-align: center;
          padding: 40px;
          font-size: 18px;
          color: #666;
        }
        
        .error-container {
          text-align: center;
          padding: 40px;
          max-width: 500px;
          margin: 100px auto;
          background: white;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .error-container button {
          margin-top: 20px;
          padding: 10px 20px;
          background: #2196f3;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 16px;
        }
        
        .error {
          text-align: center;
          padding: 40px;
          font-size: 18px;
          color: #f44336;
        }
        
        @media (max-width: 768px) {
          .emergency-header {
            flex-direction: column;
            align-items: flex-start;
          }
          
          .emergency-info {
            flex-wrap: wrap;
          }
          
          .actions {
            flex-direction: column;
          }
          
          .action-btn {
            width: 100%;
          }
        }
      `}</style>
    </div>
  );
};

export default EmergencyDashboard;
