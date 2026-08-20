import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Circle } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

// Fix Leaflet default marker icons
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

// Custom emergency marker
const emergencyIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const LiveLocationTracker = ({ 
  userId, 
  isEmergency = false, 
  emergencyEventId = null,
  apiUrl,
  onLocationUpdate = null 
}) => {
  const [location, setLocation] = useState(null);
  const [locationHistory, setLocationHistory] = useState([]);
  const [watchId, setWatchId] = useState(null);
  const [isTracking, setIsTracking] = useState(false);
  const [error, setError] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const wsRef = useRef(null);
  const mapRef = useRef(null);

  // Get user's current location
  const startTracking = () => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser');
      return;
    }

    setError(null);
    setIsTracking(true);

    const id = navigator.geolocation.watchPosition(
      (position) => {
        const { latitude, longitude, accuracy, altitude, speed, heading } = position.coords;
        const newLocation = {
          latitude,
          longitude,
          accuracy,
          altitude,
          speed,
          heading,
          timestamp: new Date().toISOString()
        };
        
        setLocation(newLocation);
        
        // Send to backend
        sendLocationToBackend(newLocation);
        
        // Callback for parent component
        if (onLocationUpdate) {
          onLocationUpdate(newLocation);
        }
      },
      (error) => {
        console.error('Geolocation error:', error);
        setError(`Error getting location: ${error.message}`);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0
      }
    );

    setWatchId(id);
  };

  const stopTracking = () => {
    if (watchId) {
      navigator.geolocation.clearWatch(watchId);
      setWatchId(null);
    }
    setIsTracking(false);
  };

  // Send location to backend
  const sendLocationToBackend = async (location) => {
    try {
      const response = await fetch('/api/location/update/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          ...location,
          is_emergency: isEmergency,
          emergency_event_id: emergencyEventId
        })
      });

      if (!response.ok) {
        throw new Error('Failed to send location');
      }
    } catch (error) {
      console.error('Error sending location:', error);
    }
  };

  // WebSocket connection for receiving location updates
  const connectWebSocket = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return;
    }

    const token = localStorage.getItem('access_token');
    if (!token) {
      setError('Authentication required');
      return;
    }

    const defaultUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/location/`;
    const url = new URL(apiUrl || defaultUrl);
    url.searchParams.set('token', token);
    const ws = new WebSocket(url.toString());
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionStatus('connected');
      console.log('WebSocket connected');
      
      // Request location history
      ws.send(JSON.stringify({
        type: 'get_location_history',
        user_id: userId
      }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
          case 'location_update':
          case 'emergency_location':
            const loc = data.location;
            setLocation({
              latitude: loc.latitude,
              longitude: loc.longitude,
              timestamp: loc.timestamp
            });
            
            // Add to history
            setLocationHistory(prev => [...prev, loc].slice(-100)); // Keep last 100
            break;
            
          case 'location_history':
            setLocationHistory(data.locations || []);
            break;
            
          case 'initial_location':
            const initialLoc = data.location;
            if (initialLoc) {
              setLocation({
                latitude: initialLoc.latitude,
                longitude: initialLoc.longitude,
                timestamp: initialLoc.timestamp
              });
            }
            break;
            
          default:
            console.log('Unknown message type:', data.type);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onclose = () => {
      setConnectionStatus('disconnected');
      console.log('WebSocket disconnected');
      
      // Attempt to reconnect after 5 seconds
      setTimeout(connectWebSocket, 5000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('error');
    };
  };

  useEffect(() => {
    // Connect WebSocket when component mounts
    connectWebSocket();

    // Start tracking if emergency
    if (isEmergency) {
      startTracking();
    }

    // Cleanup on unmount
    return () => {
      stopTracking();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [userId, isEmergency]);

  // Fit map to show all markers
  const fitMapToLocations = () => {
    if (mapRef.current && location) {
      const map = mapRef.current;
      const bounds = L.latLngBounds([
        [location.latitude, location.longitude]
      ]);
      
      // Add history points to bounds
      locationHistory.forEach(point => {
        bounds.extend([point.latitude, point.longitude]);
      });
      
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  };

  useEffect(() => {
    if (location) {
      fitMapToLocations();
    }
  }, [location, locationHistory]);

  return (
    <div className="live-location-tracker">
      <div className="tracker-controls">
        <div className="status-indicator">
          <span className={`status-dot ${connectionStatus}`}></span>
          <span className="status-text">
            {connectionStatus === 'connected' ? 'Connected' : 
             connectionStatus === 'connecting' ? 'Connecting...' : 
             connectionStatus === 'error' ? 'Error' : 'Disconnected'}
          </span>
        </div>
        
        {!isEmergency && (
          <div className="controls">
            <button 
              onClick={isTracking ? stopTracking : startTracking}
              className={`track-btn ${isTracking ? 'active' : ''}`}
            >
              {isTracking ? 'Stop Tracking' : 'Start Tracking'}
            </button>
          </div>
        )}
        
        {error && (
          <div className="error-message">
            ⚠️ {error}
          </div>
        )}
        
        {isEmergency && (
          <div className="emergency-badge">
            🚨 EMERGENCY TRACKING ACTIVE
          </div>
        )}
      </div>

      <div className="map-container">
        <MapContainer
          center={[20, 0]}
          zoom={2}
          style={{ height: '500px', width: '100%' }}
          ref={mapRef}
          scrollWheelZoom={true}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          
          {location && (
            <>
              {/* Accuracy circle */}
              {location.accuracy && (
                <Circle
                  center={[location.latitude, location.longitude]}
                  radius={location.accuracy}
                  pathOptions={{
                    color: isEmergency ? 'red' : 'blue',
                    fillColor: isEmergency ? 'red' : 'blue',
                    fillOpacity: 0.1,
                    weight: 2
                  }}
                />
              )}
              
              {/* Current location marker */}
              <Marker 
                position={[location.latitude, location.longitude]}
                icon={isEmergency ? emergencyIcon : undefined}
              >
                <Popup>
                  <div>
                    <h4>{isEmergency ? '🚨 Emergency Location' : 'Current Location'}</h4>
                    <p>Lat: {location.latitude.toFixed(6)}</p>
                    <p>Lng: {location.longitude.toFixed(6)}</p>
                    {location.accuracy && <p>Accuracy: {location.accuracy.toFixed(0)}m</p>}
                    <p>Time: {new Date(location.timestamp).toLocaleString()}</p>
                    {isEmergency && <p className="emergency-text">⚠️ Emergency Active</p>}
                  </div>
                </Popup>
              </Marker>
            </>
          )}
          
          {/* Location history path */}
          {locationHistory.length > 1 && (
            <Polyline
              positions={locationHistory.map(point => [point.latitude, point.longitude])}
              pathOptions={{
                color: isEmergency ? 'red' : 'blue',
                opacity: 0.7,
                weight: 3,
                dashArray: isEmergency ? '10, 5' : null
              }}
            />
          )}
          
          {/* History markers (every 5th point) */}
          {locationHistory.map((point, index) => {
            if (index % 5 === 0) {
              return (
                <Marker
                  key={index}
                  position={[point.latitude, point.longitude]}
                  icon={L.divIcon({
                    className: 'history-marker',
                    html: '•',
                    iconSize: [10, 10],
                    iconAnchor: [5, 5]
                  })}
                />
              );
            }
            return null;
          })}
        </MapContainer>
      </div>

      <style jsx>{`
        .live-location-tracker {
          background: white;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
          overflow: hidden;
        }
        
        .tracker-controls {
          padding: 16px;
          background: #f5f5f5;
          border-bottom: 1px solid #ddd;
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 10px;
        }
        
        .status-indicator {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        
        .status-dot {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          display: inline-block;
        }
        
        .status-dot.connected {
          background: #4CAF50;
        }
        
        .status-dot.disconnected {
          background: #f44336;
        }
        
        .status-dot.connecting {
          background: #FFC107;
        }
        
        .status-dot.error {
          background: #f44336;
        }
        
        .track-btn {
          padding: 8px 16px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-weight: bold;
          background: #2196F3;
          color: white;
        }
        
        .track-btn.active {
          background: #f44336;
        }
        
        .track-btn:hover {
          opacity: 0.9;
        }
        
        .emergency-badge {
          background: #f44336;
          color: white;
          padding: 8px 16px;
          border-radius: 4px;
          font-weight: bold;
          animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
          0% { opacity: 1; }
          50% { opacity: 0.5; }
          100% { opacity: 1; }
        }
        
        .error-message {
          color: #f44336;
          padding: 8px;
          background: #ffebee;
          border-radius: 4px;
          width: 100%;
        }
        
        .map-container {
          width: 100%;
          height: 500px;
        }
        
        .emergency-text {
          color: #f44336;
          font-weight: bold;
        }
        
        .history-marker {
          background: none;
          border: none;
          color: #666;
          font-size: 14px;
        }
      `}</style>
    </div>
  );
};

export default LiveLocationTracker;
