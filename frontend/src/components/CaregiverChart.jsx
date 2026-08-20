import { useEffect, useState } from 'react';
import {
  ResponsiveContainer, ComposedChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceDot, Legend,
} from 'recharts';
import api from '../api';
import { usePatient } from '../contexts/PatientContext';

function formatDuration(minutes) {
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const hrs = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  return `${hrs}h ${mins}m`;
}

export default function CaregiverChart({ refreshKey }) {
  const { patientQueryParam } = usePatient();
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.get('/vitals/daily-chart/', { params: { days: 7, ...patientQueryParam } })
      .then((res) => { if (!cancelled) { setData(res.data); setError(false); } })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [patientQueryParam.patient_id, refreshKey]);

  if (error) {
    return <p style={{ color: 'var(--color-text-muted)' }}>Could not load the chart data.</p>;
  }
  if (!data) {
    return <p style={{ color: 'var(--color-text-muted)' }}>Loading chart…</p>;
  }
  if (!data.timeline || data.timeline.length === 0) {
    return <p style={{ color: 'var(--color-text-muted)' }}>No readings in the last 7 days yet.</p>;
  }

  // Build a combined per-reading risk series (from Predictions) for the line,
  // and map alert markers onto matching x-axis points for overlay dots.
  const chartData = data.timeline.map((point, idx) => ({
    idx,
    time: new Date(point.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    timestamp: point.timestamp,
    riskScore: point.risk_score,
    isHigh: point.risk_level === 'high',
  }));

  const alertDots = data.alert_markers.map((alert) => {
    // find nearest chart point in time for placement
    const alertTime = new Date(alert.timestamp).getTime();
    let nearest = chartData[0];
    let bestDiff = Infinity;
    for (const point of chartData) {
      const diff = Math.abs(new Date(point.timestamp).getTime() - alertTime);
      if (diff < bestDiff) { bestDiff = diff; nearest = point; }
    }
    return { ...alert, idx: nearest?.idx ?? 0, riskScore: nearest?.riskScore ?? 0 };
  });

  return (
    <div>
      <div className="card-grid" style={{ marginBottom: 16 }}>
        <div>
          <div className="stat-label">% time in high risk (7d)</div>
          <div className="stat-value">{data.pct_time_high_risk}<span className="stat-unit">%</span></div>
        </div>
        <div>
          <div className="stat-label">High-risk episodes</div>
          <div className="stat-value">{data.episode_count}</div>
        </div>
        <div>
          <div className="stat-label">Longest episode</div>
          <div className="stat-value" style={{ fontSize: 22 }}>
            {data.episodes.length > 0
              ? formatDuration(Math.max(...data.episodes.map((e) => e.duration_minutes)))
              : '—'}
          </div>
        </div>
        <div>
          <div className="stat-label">Alerts (7d)</div>
          <div className="stat-value">{data.alert_markers.length}</div>
        </div>
      </div>

      {data.daily_series.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div className="stat-label" style={{ marginBottom: 8 }}>Daily mean / peak heart rate</div>
          <ResponsiveContainer width="100%" height={160}>
            <ComposedChart data={data.daily_series}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} domain={['dataMin - 10', 'dataMax + 10']} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="mean_heart_rate" name="Mean HR" stroke="var(--color-accent)" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="peak_heart_rate" name="Peak HR" stroke="var(--color-risk-high)" strokeWidth={2} dot={false} strokeDasharray="4 3" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      <div>
        <div className="stat-label" style={{ marginBottom: 8 }}>Risk score over time, with alerts overlaid</div>
        <ResponsiveContainer width="100%" height={200}>
          <ComposedChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="riskScore"
              name="Risk score"
              stroke="var(--color-primary)"
              strokeWidth={2}
              dot={(props) => {
                const { cx, cy, payload } = props;
                return payload.isHigh
                  ? <circle key={`dot-${payload.idx}`} cx={cx} cy={cy} r={3} fill="var(--color-risk-high)" />
                  : <circle key={`dot-${payload.idx}`} cx={cx} cy={cy} r={0} />;
              }}
            />
            {alertDots.map((alert) => (
              <ReferenceDot
                key={alert.id}
                x={chartData[alert.idx]?.time}
                y={alert.riskScore}
                r={6}
                fill={alert.severity === 'high' ? 'var(--color-risk-high)' : '#E0A93A'}
                stroke="white"
                strokeWidth={1.5}
                isFront
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
        {data.alert_markers.length > 0 && (
          <div style={{ marginTop: 8, fontSize: 12, color: 'var(--color-text-muted)' }}>
            ● markers show where an alert fired — hover the point for the risk score at that moment.
          </div>
        )}
      </div>
    </div>
  );
}
