import { useState, useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Circle } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

/*
 * LivePatientMap
 *
 * A guardian-side map that polls the patient's recent location history every
 * 3 seconds and shows their live marker + movement trail. Uses the existing
 * /api/location/history/?user_id=... endpoint (guardian-permission enforced
 * on the backend).
 *
 * To simulate movement on a desktop: Chrome DevTools → Sensors → Override
 * geolocation → drag the coordinates.
 */
const POLL_MS = 3000;

const LivePatientMap = ({ patientId, patientName }) => {
  const [history, setHistory] = useState([]); // [{lat, lng, timestamp, accuracy}]
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mapRef = useRef(null);

  const fetchLocations = useCallback(async () => {
    if (!patientId) return;
    try {
      const token = localStorage.getItem('access_token');
      if (!token) return;
      const res = await fetch(`/api/location/history/?user_id=${patientId}&limit=50`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setError(res.status === 404 || res.status === 403 ? 'No access to location' : `Error ${res.status}`);
        setHistory([]);
        setLoading(false);
        return;
      }
      const data = await res.json();
      // ListAPIView paginates: {count, results:[...]}. Handle both shapes.
      const list = Array.isArray(data) ? data : data.results || [];
      setHistory(
        list.map((loc) => ({
          lat: Number(loc.latitude),
          lng: Number(loc.longitude),
          timestamp: loc.timestamp,
          accuracy: loc.accuracy,
        }))
      );
      setError(null);
      setLoading(false);
      setLastUpdated(new Date());
    } catch (e) {
      console.error('[MAP] poll failed:', e);
      setError('Could not load patient location');
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    setHistory([]);
    setLoading(true);
    fetchLocations();
    const id = setInterval(fetchLocations, POLL_MS);
    return () => clearInterval(id);
  }, [fetchLocations]);

  const latest = history[0]; // history comes back newest-first
  const trail = history.map((h) => [h.lat, h.lng]).filter(([a, b]) => Number.isFinite(a) && Number.isFinite(b));

  return (
    <div className="live-patient-map">
      <div className="lpm-header">
        <h4 style={{ margin: 0 }}>
          📍 Live Location {patientName ? `— ${patientName}` : ''}
        </h4>
        {latest && (
          <span className="lpm-last">
            updated {lastUpdated ? lastUpdated.toLocaleTimeString() : ''} · {history.length} fixes
          </span>
        )}
      </div>

      {!patientId ? (
        <div className="lpm-empty">Select a patient to see their live location.</div>
      ) : loading ? (
        <div className="lpm-empty">Loading location…</div>
      ) : error || !latest ? (
        <div className="lpm-empty">
          {error || 'Waiting for the patient to share their location…'}
          <div className="lpm-hint">
            Patient should keep their dashboard open and allow location access.
          </div>
        </div>
      ) : (
        <MapContainer
          ref={mapRef}
          center={[latest.lat, latest.lng]}
          zoom={15}
          scrollWheelZoom={false}
          style={{ height: 300, width: '100%', borderRadius: 8 }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {latest.accuracy != null && (
            <Circle
              center={[latest.lat, latest.lng]}
              radius={latest.accuracy}
              pathOptions={{ color: '#1976d2', fillColor: '#1976d2', fillOpacity: 0.08, weight: 1 }}
            />
          )}
          {trail.length > 1 && (
            <Polyline
              positions={trail}
              pathOptions={{ color: '#1976d2', opacity: 0.6, weight: 3, dashArray: '8, 6' }}
            />
          )}
          <Marker position={[latest.lat, latest.lng]}>
            <Popup>
              <strong>{patientName || 'Patient'}</strong>
              <div>{latest.lat.toFixed(6)}, {latest.lng.toFixed(6)}</div>
              {latest.accuracy != null && <div>Accuracy ≈ {Math.round(latest.accuracy)} m</div>}
              {latest.timestamp && (
                <div>{new Date(latest.timestamp).toLocaleString()}</div>
              )}
            </Popup>
          </Marker>
        </MapContainer>
      )}

      <style>{`
        .live-patient-map {
          background: white;
          border: 1px solid #e0e0e0;
          border-radius: 10px;
          padding: 12px;
          margin-top: 14px;
        }
        .lpm-header {
          display: flex; justify-content: space-between; align-items: center;
          flex-wrap: wrap; gap: 6px; margin-bottom: 10px;
        }
        .lpm-header h4 { color: #263238; }
        .lpm-last { font-size: 12px; color: #78909c; }
        .lpm-empty {
          text-align: center; padding: 28px; color: #607d8b; font-size: 14px;
          background: #fafafa; border-radius: 8px;
        }
        .lpm-hint { margin-top: 6px; font-size: 12px; color: #90a4ae; }
      `}</style>
    </div>
  );
};

export default LivePatientMap;