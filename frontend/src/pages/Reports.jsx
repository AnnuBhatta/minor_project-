import { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import api from '../api';

export default function Reports() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/vitals/weekly-report/').then((res) => setReport(res.data)).catch(() => setError('Unable to load weekly report'));
  }, []);

  return (
    <Layout>
      <div className="page-header">
        <h1>Weekly Report</h1>
        <p>A quick overview of patient risk and average vitals</p>
      </div>

      <div className="card report-card">
        {error && <p>{error}</p>}
        {!report && !error && <p>Loading report...</p>}
        {report && (
          <>
            <div className="report-grid">
              <div>
                <div className="report-label">Average Heart Rate</div>
                <div className="report-value">{report.average_heart_rate?.toFixed(1)} bpm</div>
              </div>
              <div>
                <div className="report-label">Average SpO₂</div>
                <div className="report-value">{report.average_spo2?.toFixed(1)}%</div>
              </div>
              <div>
                <div className="report-label">High-risk readings</div>
                <div className="report-value">{report.high_risk_readings ?? 0}</div>
              </div>
              <div>
                <div className="report-label">Weekly readings</div>
                <div className="report-value">{report.total_readings ?? 0}</div>
              </div>
            </div>
            <div style={{ marginTop: 20, color: '#5C6E71' }}>
              <p>Most recent status: {report.last_status}</p>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
