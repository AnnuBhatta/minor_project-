import { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import EcgLine from '../components/EcgLine';
import PatientSelector from '../components/PatientSelector';
import DemoControls from '../components/DemoControls';
import CaregiverChart from '../components/CaregiverChart';
import api from '../api';
import { usePatient } from '../contexts/PatientContext';

export default function Dashboard() {
  const { patientQueryParam } = usePatient();
  const [latest, setLatest] = useState(null);
  const [error, setError] = useState(false);
  const [chartRefreshKey, setChartRefreshKey] = useState(0);

  const fetchLatest = async () => {
    try {
      const res = await api.get('/vitals/latest/', { params: patientQueryParam });
      setLatest(res.data);
      setError(false);
    } catch {
      setError(true);
    }
  };

  useEffect(() => {
    fetchLatest();
    const interval = setInterval(fetchLatest, 5000);
    return () => clearInterval(interval);
  }, [patientQueryParam.patient_id]);

  const isHigh = latest?.risk_category === 'high';

  return (
    <Layout>
      <div className="page-header">
        <h1>Live Status</h1>
        <p>Real-time vitals, refreshed every 5 seconds</p>
      </div>

      <PatientSelector />
      <DemoControls onTick={() => setChartRefreshKey((key) => key + 1)} />

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <EcgLine color={isHigh ? '#C1443C' : '#2FA8A0'} />
          <span className="ecg-live">
            <span className="pulse-dot" />Live
          </span>
        </div>

        {error && <p style={{ color: '#5C6E71' }}>Could not reach the server. Is it running?</p>}
        {!error && !latest && <p style={{ color: '#5C6E71' }}>No readings yet — send a test reading or run a demo scenario to get started.</p>}

        {latest && (
          <>
            <div style={{ marginBottom: 18 }}>
              <span className={`risk-badge ${latest.risk_category}`}>
                <span className="dot" />
                {latest.risk_category === 'high' ? 'High Risk' : 'Low Risk'}
              </span>
            </div>
            <div className="card-grid">
              <div>
                <div className="stat-label">Heart Rate</div>
                <div className="stat-value">{latest.heart_rate}<span className="stat-unit">bpm</span></div>
              </div>
              <div>
                <div className="stat-label">SpO₂</div>
                <div className="stat-value">{latest.spo2}<span className="stat-unit">%</span></div>
              </div>
              <div>
                <div className="stat-label">Blood Pressure</div>
                <div className="stat-value">{latest.systolic_bp}/{latest.diastolic_bp}</div>
              </div>
              <div>
                <div className="stat-label">Mean Arterial Pressure</div>
                <div className="stat-value">{latest.derived_map ?? '—'}</div>
              </div>
            </div>
          </>
        )}
      </div>

      <div className="card">
        <div className="stat-label" style={{ marginBottom: 12, fontSize: 15 }}>Caregiver overview (last 7 days)</div>
        <CaregiverChart refreshKey={chartRefreshKey} />
      </div>
    </Layout>
  );
}
