import { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import api from '../api';

export default function Trend() {
  const [trend, setTrend] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/vitals/trend/').then((res) => setTrend(res.data)).catch(() => setError('Unable to load trend data'));
  }, []);

  return (
    <Layout>
      <div className="page-header">
        <h1>Health Trend</h1>
        <p>Trend analysis for vitals and risk over time</p>
      </div>

      <div className="card">
        {error && <p>{error}</p>}
        {!trend && !error && <p>Loading trend data...</p>}
        {trend && trend.trend === 'insufficient_data' && (
          <p>{trend.message}</p>
        )}
        {trend && trend.trend !== 'insufficient_data' && (
          <div>
            <div className="card-grid">
              <div>
                <div className="stat-label">Trend</div>
                <div className="stat-value">{trend.trend.replace('_', ' ')}</div>
              </div>
              <div>
                <div className="stat-label">Recent Avg HR</div>
                <div className="stat-value">{trend.average_heart_rate_recent} bpm</div>
              </div>
              <div>
                <div className="stat-label">Previous Avg HR</div>
                <div className="stat-value">{trend.average_heart_rate_previous} bpm</div>
              </div>
            </div>
            <p style={{ marginTop: 18, color: '#5C6E71' }}>{trend.note}</p>
          </div>
        )}
      </div>
    </Layout>
  );
}
