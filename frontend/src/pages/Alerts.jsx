import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import Layout from '../components/Layout';
import api from '../api';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/alerts/').then((res) => setAlerts(res.data)).catch(() => setError('Unable to load alerts'));
  }, []);

  const validAlerts = alerts.filter((alert) => alert.latitude != null && alert.longitude != null);

  return (
    <Layout>
      <div className="page-header">
        <h1>Alerts & Map</h1>
        <p>Emergency alert activity from patients in the system</p>
      </div>

      <div className="card">
        {error && <p>{error}</p>}
        {alerts.length === 0 && !error && <p>No active alerts at the moment.</p>}
        {alerts.length > 0 && (
          <>
            <ul className="alert-list">
              {alerts.map((alert) => (
                <li key={alert.id}>
                  <div>
                    <strong>{alert.user || 'Patient'}</strong>
                    <span className={alert.resolved ? 'resolved' : 'unresolved'}>{alert.resolved ? 'Resolved' : 'Active'}</span>
                  </div>
                  <div>{new Date(alert.created_at).toLocaleString()}</div>
                  <div>High-risk alert from reading {alert.reading || 'N/A'}</div>
                  <div className="alert-geo">
                    {alert.latitude ?? 'unknown'}, {alert.longitude ?? 'unknown'}
                  </div>
                </li>
              ))}
            </ul>
            {validAlerts.length > 0 && (
              <div className="card" style={{ marginTop: 20, padding: 0, overflow: 'hidden' }}>
                <MapContainer
                  center={[validAlerts[0].latitude, validAlerts[0].longitude]}
                  zoom={10}
                  scrollWheelZoom={false}
                  style={{ height: 360, width: '100%' }}
                >
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  {validAlerts.map((alert) => (
                    <Marker key={alert.id} position={[alert.latitude, alert.longitude]}>
                      <Popup>
                        <strong>{alert.user || 'Patient'}</strong>
                        <div>{alert.resolved ? 'Resolved' : 'Active'}</div>
                        <div>{new Date(alert.created_at).toLocaleString()}</div>
                      </Popup>
                    </Marker>
                  ))}
                </MapContainer>
              </div>
            )}
          </>
        )}
      </div>
    </Layout>
  );
}
