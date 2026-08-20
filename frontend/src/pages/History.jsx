import { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import api from '../api';

export default function History() {
  const [readings, setReadings] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/vitals/history/').then((res) => setReadings(res.data)).catch(() => setError('Unable to fetch history'));
  }, []);

  return (
    <Layout>
      <div className="page-header">
        <h1>History</h1>
        <p>Recent vital readings for the last 30 days</p>
      </div>

      <div className="card">
        {error && <p>{error}</p>}
        {!error && readings.length === 0 && <p>No history available yet.</p>}
        {readings.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>HR</th>
                <th>SpO₂</th>
                <th>BP</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {readings.map((reading) => (
                <tr key={reading.id}>
                  <td>{new Date(reading.timestamp).toLocaleString()}</td>
                  <td>{reading.heart_rate}</td>
                  <td>{reading.spo2}</td>
                  <td>{reading.systolic_bp}/{reading.diastolic_bp}</td>
                  <td>{reading.risk_category}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Layout>
  );
}
