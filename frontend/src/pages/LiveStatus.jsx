import { useEffect, useRef, useState } from 'react';
import Layout from '../components/Layout';
import api from '../api';
import { usePatient } from '../contexts/PatientContext';

/*
 * Real-time vitals dashboard.
 *
 * Polls GET /api/vitals/latest/ every 5 seconds (JWT added by the `api`
 * interceptor). Shows a spinner while loading, an error banner if the fetch
 * fails, and falls back to demo data so the page always renders something.
 */

const DEMO_VITALS = {
  heart_rate: 76,
  systolic_bp: 118,
  diastolic_bp: 76,
  oxygen_saturation: 98,
  risk_category: 'low',
  timestamp: null,
};

const METRICS = [
  { key: 'heart_rate', label: 'Heart Rate', unit: 'bpm', low: 60, high: 100 },
  { key: 'oxygen_saturation', label: 'Oxygen Saturation', unit: '%', low: 95, high: null },
];

const BP_NORMAL = { sysLow: 90, sysHigh: 140, diaLow: 60, diaHigh: 90 };

function checkStatus(value, { low, high }) {
  if (value == null || Number.isNaN(Number(value))) {
    return { level: 'muted', label: 'No data' };
  }
  if (high != null && Number(value) > high) return { level: 'high', label: 'High' };
  if (low != null && Number(value) < low) return { level: 'low', label: 'Low' };
  return { level: 'normal', label: 'Normal' };
}

function checkBp(systolic, diastolic) {
  if (systolic == null && diastolic == null) return { level: 'muted', label: 'No data' };
  const sys = Number(systolic);
  const dia = Number(diastolic);
  if (!Number.isNaN(sys) && sys >= BP_NORMAL.sysHigh) return { level: 'high', label: 'High' };
  if (!Number.isNaN(dia) && dia >= BP_NORMAL.diaHigh) return { level: 'high', label: 'High' };
  if (!Number.isNaN(sys) && sys < BP_NORMAL.sysLow) return { level: 'low', label: 'Low' };
  if (!Number.isNaN(dia) && dia < BP_NORMAL.diaLow) return { level: 'low', label: 'Low' };
  return { level: 'normal', label: 'Normal' };
}

function fmt(value, digits = 0) {
  if (value == null || Number.isNaN(Number(value))) return '—';
  return Number(value).toFixed(digits);
}

function MetricCard({ label, value, unit, status, sub }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">
        {value}
        {unit && <span className="stat-unit">{unit}</span>}
      </div>
      {sub && <div className="metric-sub">{sub}</div>}
      <span className={`metric-status ${status.level}`}>{status.label}</span>
    </div>
  );
}

function healthSummary(vitals, riskLevel) {
  if (riskLevel === 'high') {
    return 'Vitals are outside the safe range — high risk. Contact emergency services or alert a guardian immediately.';
  }
  const abnormal = [
    checkStatus(vitals.heart_rate, METRICS[0]),
    checkBp(vitals.systolic_bp, vitals.diastolic_bp),
    checkStatus(vitals.oxygen_saturation ?? vitals.spo2, METRICS[1]),
  ].filter((s) => s.level === 'high' || s.level === 'low');

  if (abnormal.length > 0) {
    return 'Some vitals are outside the normal range — monitor closely and consider consulting a healthcare provider.';
  }
  return 'All vitals are within normal range — everything looks good.';
}

function formatTimestamp(ts) {
  if (!ts) return 'No readings yet';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return 'No readings yet';
  return `${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} · ${d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
}

export default function LiveStatus() {
  const { patientQueryParam } = usePatient();
  const [vitals, setVitals] = useState(null);
  const [loading, setLoading] = useState(true);
  const [usingDemo, setUsingDemo] = useState(false);
  const [offline, setOffline] = useState(false);
  const hasRealDataRef = useRef(false);

  const fetchLatest = async () => {
    try {
      const res = await api.get('/vitals/latest/', { params: patientQueryParam });
      setVitals(res.data || null);
      if (res.data) hasRealDataRef.current = true;
      setUsingDemo(false);
      setOffline(false);
    } catch {
      setOffline(true);
      if (!hasRealDataRef.current) {
        setVitals({ ...DEMO_VITALS, timestamp: new Date().toISOString() });
        setUsingDemo(true);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLatest();
    const interval = setInterval(fetchLatest, 5000);
    return () => clearInterval(interval);
  }, [patientQueryParam.patient_id]);

  const riskLevel = vitals?.risk_category === 'high' ? 'high' : 'low';

  if (loading && !vitals) {
    return (
      <Layout>
        <div className="page-header">
          <h1>Live Status</h1>
        </div>
        <div className="loading-wrap">
          <div className="spinner" />
          <p>Loading live vitals…</p>
        </div>
      </Layout>
    );
  }

  const bpStatus = checkBp(vitals?.systolic_bp, vitals?.diastolic_bp);

  return (
    <Layout>
      <div className="page-header">
        <h1>Live Status</h1>
      </div>

      {(usingDemo || offline) && (
        <div className="demo-banner">
          {usingDemo
            ? '⚠ Server unreachable — showing demo data for testing.'
            : '⚠ Server unreachable — showing the last live values.'}
        </div>
      )}

      <div className="live-toolbar">
        <span className={`risk-badge ${riskLevel}`}>
          <span className="dot" />
          {riskLevel === 'high' ? 'High Risk' : 'Low Risk'}
        </span>
        <span className="ecg-live">
          <span className="pulse-dot" />
          {usingDemo ? 'Demo' : 'Live'}
        </span>
        <span className="live-updated">Updated {formatTimestamp(vitals?.timestamp)}</span>
      </div>

      <div className="card-grid live-grid">
        <MetricCard
          label="Heart Rate"
          value={fmt(vitals?.heart_rate)}
          unit="bpm"
          status={checkStatus(vitals?.heart_rate, METRICS[0])}
        />
        <MetricCard
          label="Blood Pressure"
          value={`${fmt(vitals?.systolic_bp)}/${fmt(vitals?.diastolic_bp)}`}
          unit="mmHg"
          status={bpStatus}
          sub={vitals?.derived_map != null ? `MAP ${fmt(vitals.derived_map, 1)}` : null}
        />
        <MetricCard
          label="Oxygen Saturation"
          value={fmt(vitals?.oxygen_saturation ?? vitals?.spo2)}
          unit="%"
          status={checkStatus(vitals?.oxygen_saturation ?? vitals?.spo2, METRICS[1])}
        />
      </div>

      <div className="card live-summary">
        <div className="metric-label">Health Summary</div>
        <p className="live-summary-text">
          {vitals ? healthSummary(vitals, riskLevel) : 'No readings available yet.'}
        </p>
        <div className="live-legend">
          <span><span className="dot" style={{ background: 'var(--color-risk-low)' }} />Normal</span>
          <span><span className="dot" style={{ background: 'var(--color-warning)' }} />Borderline / Low</span>
          <span><span className="dot" style={{ background: 'var(--color-risk-high)' }} />High</span>
        </div>
      </div>
    </Layout>
  );
}