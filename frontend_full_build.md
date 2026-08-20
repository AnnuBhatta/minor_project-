# Part J & K — Full Frontend Build (Backend Additions + Complete Dashboard)

This continues from Step 29 in the main guide. We add two small backend endpoints your new
frontend needs, then build a complete, professionally designed dashboard connected to your
real Django API.

**Design system used below** (so every file stays visually consistent):
- Colors: background `#F7F9FA`, surface `#FFFFFF`, primary `#0B5D6B` (deep clinical teal),
  primary-dark `#073E47`, accent `#2FA8A0`, risk-high `#C1443C`, risk-low `#3F8F5F`,
  text `#1B2B2E`, text-muted `#5C6E71`, border `#E1E7E8`
- Fonts: **Space Grotesk** for headings, **Inter** for body text, **IBM Plex Mono** for vital
  number readouts (so they read like real clinical data)
- Signature element: a subtle ECG/heartbeat waveform used as a divider and "live" indicator

---

## PART J — BACKEND ADDITIONS

### Step 30: Weekly report endpoint

Open `vitals/views.py` and add this at the bottom:

```python
from django.db.models import Avg, Count, Max, Min
from django.db.models.functions import TruncWeek
from rest_framework.views import APIView
from rest_framework.response import Response
from alerts.models import EmergencyAlert

class WeeklyReportView(APIView):
    """GET /api/vitals/weekly-report/"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        readings = (
            VitalReading.objects.filter(user=request.user)
            .annotate(week=TruncWeek('timestamp'))
            .values('week')
            .annotate(
                avg_hr=Avg('heart_rate'),
                max_hr=Max('heart_rate'),
                min_hr=Min('heart_rate'),
                avg_spo2=Avg('spo2'),
                reading_count=Count('id'),
            )
            .order_by('-week')[:8]  # last 8 weeks
        )

        alert_counts = (
            EmergencyAlert.objects.filter(user=request.user)
            .annotate(week=TruncWeek('created_at'))
            .values('week')
            .annotate(alert_count=Count('id'))
        )
        alert_map = {a['week']: a['alert_count'] for a in alert_counts}

        data = []
        for r in readings:
            data.append({
                "week": r['week'],
                "avg_heart_rate": round(r['avg_hr'], 1) if r['avg_hr'] else None,
                "max_heart_rate": r['max_hr'],
                "min_heart_rate": r['min_hr'],
                "avg_spo2": round(r['avg_spo2'], 1) if r['avg_spo2'] else None,
                "reading_count": r['reading_count'],
                "alert_count": alert_map.get(r['week'], 0),
            })
        return Response(data)
```

### Step 31: Trend endpoint (placeholder until LSTM is trained)

This gives your frontend something real to show in the "Health Trend Prediction" section
now, and you swap the inside of this function for your LSTM call later — the API shape
won't need to change.

Add to `vitals/views.py`:

```python
class TrendView(APIView):
    """GET /api/vitals/trend/ -- simple trend signal until LSTM model is ready"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        recent = list(
            VitalReading.objects.filter(user=request.user).order_by('-timestamp')[:10]
        )
        if len(recent) < 6:
            return Response({"trend": "insufficient_data", "message": "Need more readings to assess trend."})

        recent.reverse()  # oldest to newest
        first_half = recent[:len(recent)//2]
        second_half = recent[len(recent)//2:]

        avg_first = sum(r.heart_rate for r in first_half) / len(first_half)
        avg_second = sum(r.heart_rate for r in second_half) / len(second_half)
        high_risk_count = sum(1 for r in second_half if r.risk_category == "high")

        if high_risk_count >= 2:
            trend = "high_risk"
        elif avg_second - avg_first > 8:
            trend = "increasing_risk"
        else:
            trend = "stable"

        return Response({
            "trend": trend,  # "stable" | "increasing_risk" | "high_risk"
            "avg_heart_rate_recent": round(avg_second, 1),
            "avg_heart_rate_previous": round(avg_first, 1),
            "note": "Rule-based estimate — will be replaced by LSTM model."
        })
```

### Step 32: Wire up the new URLs

Open `vitals/urls.py` and replace it with:

```python
from django.urls import path
from .views import VitalReadingCreateView, LatestVitalView, VitalHistoryView, WeeklyReportView, TrendView

urlpatterns = [
    path('', VitalReadingCreateView.as_view(), name='vitals-create'),
    path('latest/', LatestVitalView.as_view(), name='vitals-latest'),
    path('history/', VitalHistoryView.as_view(), name='vitals-history'),
    path('weekly-report/', WeeklyReportView.as_view(), name='vitals-weekly-report'),
    path('trend/', TrendView.as_view(), name='vitals-trend'),
]
```

Restart the server (`Ctrl+C` then `python manage.py runserver`) and confirm both new endpoints
respond (even with sparse data) before moving to the frontend.

---

## PART K — FULL FRONTEND REDESIGN

### Step 33: Install additional packages

```powershell
cd health-monitor-app\frontend
npm install react-leaflet leaflet
```

### Step 34: Add the fonts

Open `public/index.html`, and inside the `<head>` tag add:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### Step 35: Design system CSS

Create `src/styles.css`:

```css
:root {
  --color-bg: #F7F9FA;
  --color-surface: #FFFFFF;
  --color-primary: #0B5D6B;
  --color-primary-dark: #073E47;
  --color-accent: #2FA8A0;
  --color-risk-high: #C1443C;
  --color-risk-high-bg: #FBEAE9;
  --color-risk-low: #3F8F5F;
  --color-risk-low-bg: #EAF5EE;
  --color-text: #1B2B2E;
  --color-text-muted: #5C6E71;
  --color-border: #E1E7E8;
  --font-heading: 'Space Grotesk', sans-serif;
  --font-body: 'Inter', sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-body);
}

h1, h2, h3 { font-family: var(--font-heading); margin: 0 0 8px 0; }

.app-shell { display: flex; min-height: 100vh; }

/* Sidebar */
.sidebar {
  width: 220px;
  background: var(--color-primary-dark);
  color: white;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sidebar .brand {
  font-family: var(--font-heading);
  font-weight: 700;
  font-size: 18px;
  margin-bottom: 28px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.sidebar a {
  color: rgba(255,255,255,0.75);
  text-decoration: none;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
}
.sidebar a:hover { background: rgba(255,255,255,0.08); color: white; }
.sidebar a.active { background: var(--color-accent); color: white; }

/* Main content */
.main-content { flex: 1; padding: 32px 40px; max-width: 1100px; }
.page-header { margin-bottom: 24px; }
.page-header p { color: var(--color-text-muted); margin: 4px 0 0 0; }

/* Cards */
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 20px 24px;
  margin-bottom: 20px;
}
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }

.stat-label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--color-text-muted); margin-bottom: 4px; }
.stat-value { font-family: var(--font-mono); font-size: 28px; font-weight: 500; }
.stat-unit { font-size: 14px; color: var(--color-text-muted); margin-left: 4px; }

/* Risk badge */
.risk-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 14px; border-radius: 20px; font-weight: 600; font-size: 13px;
}
.risk-badge.high { background: var(--color-risk-high-bg); color: var(--color-risk-high); }
.risk-badge.low { background: var(--color-risk-low-bg); color: var(--color-risk-low); }
.risk-badge .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }

/* ECG signature element */
.ecg-line { display: block; width: 100%; height: 24px; }
.ecg-live { display: inline-flex; align-items: center; gap: 8px; font-size: 12px; color: var(--color-text-muted); }
.ecg-live .pulse-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--color-accent);
  animation: pulse 1.4s infinite;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(47,168,160,0.5); }
  70% { box-shadow: 0 0 0 8px rgba(47,168,160,0); }
  100% { box-shadow: 0 0 0 0 rgba(47,168,160,0); }
}

/* Tables */
table { width: 100%; border-collapse: collapse; }
th { text-align: left; font-size: 12px; text-transform: uppercase; color: var(--color-text-muted); padding: 8px 12px; border-bottom: 1px solid var(--color-border); }
td { padding: 12px; border-bottom: 1px solid var(--color-border); font-size: 14px; }

/* Forms */
input {
  font-family: var(--font-body);
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 14px;
  width: 100%;
}
button {
  font-family: var(--font-body);
  background: var(--color-primary);
  color: white;
  border: none;
  padding: 10px 18px;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
}
button:hover { background: var(--color-primary-dark); }

.login-shell { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--color-primary-dark); }
.login-card { background: white; padding: 40px; border-radius: 12px; width: 340px; }
```

### Step 36: A reusable ECG waveform component (the signature element)

Create `src/components/EcgLine.js`:

```javascript
export default function EcgLine({ color = "#2FA8A0" }) {
  return (
    <svg viewBox="0 0 300 40" className="ecg-line" preserveAspectRatio="none">
      <polyline
        points="0,20 40,20 55,20 65,5 75,35 85,20 100,20 140,20 155,20 165,5 175,35 185,20 220,20 260,20 275,5 285,35 295,20 300,20"
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
```

### Step 37: Sidebar layout

Create `src/components/Layout.js`:

```javascript
import { NavLink, useNavigate } from "react-router-dom";

export default function Layout({ children }) {
  const navigate = useNavigate();

  const logout = () => {
    localStorage.removeItem("access_token");
    navigate("/login");
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span style={{ color: "#2FA8A0", fontSize: 20 }}>♥</span> VitalWatch
        </div>
        <NavLink to="/dashboard" className={({isActive}) => isActive ? "active" : ""}>Live Status</NavLink>
        <NavLink to="/history" className={({isActive}) => isActive ? "active" : ""}>History</NavLink>
        <NavLink to="/alerts" className={({isActive}) => isActive ? "active" : ""}>Alerts & Map</NavLink>
        <NavLink to="/trend" className={({isActive}) => isActive ? "active" : ""}>Health Trend</NavLink>
        <NavLink to="/reports" className={({isActive}) => isActive ? "active" : ""}>Weekly Report</NavLink>
        <div style={{ flex: 1 }} />
        <a onClick={logout} style={{ cursor: "pointer" }}>Log out</a>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}
```

### Step 38: Rebuild the Login page with the new design

Replace `src/pages/Login.js`:

```javascript
import { useState } from "react";
import api from "../api";
import { useNavigate } from "react-router-dom";
import EcgLine from "../components/EcgLine";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const res = await api.post("/auth/login/", { username, password });
      localStorage.setItem("access_token", res.data.access);
      navigate("/dashboard");
    } catch {
      setError("Invalid username or password");
    }
  };

  return (
    <div className="login-shell">
      <div className="login-card">
        <EcgLine color="#0B5D6B" />
        <h2>VitalWatch</h2>
        <p style={{ color: "#5C6E71", marginTop: -8, marginBottom: 20 }}>Caregiver Dashboard</p>
        {error && <p style={{ color: "#C1443C", fontSize: 14 }}>{error}</p>}
        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: 12 }}>
            <input placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div style={{ marginBottom: 20 }}>
            <input placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <button type="submit" style={{ width: "100%" }}>Log in</button>
        </form>
      </div>
    </div>
  );
}
```

### Step 39: Rebuild the Dashboard (Live Status) page

Replace `src/pages/Dashboard.js`:

```javascript
import { useEffect, useState } from "react";
import api from "../api";
import Layout from "../components/Layout";
import EcgLine from "../components/EcgLine";

export default function Dashboard() {
  const [latest, setLatest] = useState(null);
  const [error, setError] = useState(false);

  const fetchLatest = async () => {
    try {
      const res = await api.get("/vitals/latest/");
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
  }, []);

  const isHigh = latest?.risk_category === "high";

  return (
    <Layout>
      <div className="page-header">
        <h1>Live Status</h1>
        <p>Real-time vitals, refreshed every 5 seconds</p>
      </div>

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <EcgLine color={isHigh ? "#C1443C" : "#2FA8A0"} />
          <span className="ecg-live"><span className="pulse-dot"></span>Live</span>
        </div>

        {error && <p style={{ color: "#5C6E71" }}>Could not reach the server. Is it running?</p>}
        {!error && !latest && <p style={{ color: "#5C6E71" }}>No readings yet — send a test reading to get started.</p>}

        {latest && (
          <>
            <div style={{ marginBottom: 16 }}>
              <span className={`risk-badge ${latest.risk_category}`}>
                <span className="dot"></span>
                {latest.risk_category === "high" ? "High Risk" : "Low Risk"}
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
                <div className="stat-value">{latest.derived_map ?? "—"}</div>
              </div>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
```

### Step 40: History page (charts)

Create `src/pages/History.js`:

```javascript
import { useEffect, useState } from "react";
import api from "../api";
import Layout from "../components/Layout";
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend } from "recharts";

export default function History() {
  const [data, setData] = useState([]);

  useEffect(() => {
    api.get("/vitals/history/").then((res) => {
      const formatted = res.data
        .slice()
        .reverse()
        .map((r) => ({
          ...r,
          time: new Date(r.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        }));
      setData(formatted);
    });
  }, []);

  return (
    <Layout>
      <div className="page-header">
        <h1>History</h1>
        <p>Last 100 readings</p>
      </div>

      <div className="card">
        <h3>Heart Rate (bpm)</h3>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data}>
            <CartesianGrid stroke="#E1E7E8" strokeDasharray="3 3" />
            <XAxis dataKey="time" fontSize={12} />
            <YAxis fontSize={12} />
            <Tooltip />
            <Line type="monotone" dataKey="heart_rate" stroke="#0B5D6B" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <h3>SpO₂ (%)</h3>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data}>
            <CartesianGrid stroke="#E1E7E8" strokeDasharray="3 3" />
            <XAxis dataKey="time" fontSize={12} />
            <YAxis domain={[85, 100]} fontSize={12} />
            <Tooltip />
            <Line type="monotone" dataKey="spo2" stroke="#2FA8A0" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <h3>Blood Pressure (mmHg)</h3>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data}>
            <CartesianGrid stroke="#E1E7E8" strokeDasharray="3 3" />
            <XAxis dataKey="time" fontSize={12} />
            <YAxis fontSize={12} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="systolic_bp" name="Systolic" stroke="#C1443C" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="diastolic_bp" name="Diastolic" stroke="#5C6E71" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Layout>
  );
}
```

### Step 41: Alerts + Map page

Create `src/pages/Alerts.js`:

```javascript
import { useEffect, useState } from "react";
import api from "../api";
import Layout from "../components/Layout";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    api.get("/alerts/").then((res) => setAlerts(res.data));
  }, []);

  const located = alerts.filter((a) => a.latitude && a.longitude);
  const mapCenter = located.length
    ? [located[0].latitude, located[0].longitude]
    : [27.7172, 85.324]; // fallback default center

  return (
    <Layout>
      <div className="page-header">
        <h1>Alerts & Map</h1>
        <p>Emergency events and last known location</p>
      </div>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <MapContainer center={mapCenter} zoom={located.length ? 13 : 6} style={{ height: 320, width: "100%" }}>
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {located.map((a) => (
            <Marker key={a.id} position={[a.latitude, a.longitude]}>
              <Popup>Alert #{a.id}<br />{new Date(a.created_at).toLocaleString()}</Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>

      <div className="card">
        <h3>Alert History</h3>
        {alerts.length === 0 ? (
          <p style={{ color: "#5C6E71" }}>No alerts recorded yet.</p>
        ) : (
          <table>
            <thead>
              <tr><th>ID</th><th>Date/Time</th><th>Status</th></tr>
            </thead>
            <tbody>
              {alerts.map((a) => (
                <tr key={a.id}>
                  <td>#{a.id}</td>
                  <td>{new Date(a.created_at).toLocaleString()}</td>
                  <td>{a.resolved ? "Resolved" : "Active"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Layout>
  );
}
```

> Note: your `EmergencyAlert` model needs `latitude`/`longitude` populated to show pins.
> Right now nothing sets them — that's fine for now (the table still works), and you'll fill
> those in once the Android app sends GPS data (Step 48 in the original plan).

### Step 42: Health Trend page

Create `src/pages/Trend.js`:

```javascript
import { useEffect, useState } from "react";
import api from "../api";
import Layout from "../components/Layout";

const TREND_LABELS = {
  stable: { label: "Stable", color: "#3F8F5F", bg: "#EAF5EE" },
  increasing_risk: { label: "Increasing Risk", color: "#B98900", bg: "#FBF3DC" },
  high_risk: { label: "High Risk", color: "#C1443C", bg: "#FBEAE9" },
  insufficient_data: { label: "Gathering Data", color: "#5C6E71", bg: "#F0F2F2" },
};

export default function Trend() {
  const [trend, setTrend] = useState(null);

  useEffect(() => {
    api.get("/vitals/trend/").then((res) => setTrend(res.data));
  }, []);

  if (!trend) return <Layout><p>Loading...</p></Layout>;

  const info = TREND_LABELS[trend.trend] || TREND_LABELS.insufficient_data;

  return (
    <Layout>
      <div className="page-header">
        <h1>Health Trend Prediction</h1>
        <p>Based on recent readings — will use the LSTM model once trained</p>
      </div>

      <div className="card">
        <span className="risk-badge" style={{ background: info.bg, color: info.color }}>
          <span className="dot"></span>{info.label}
        </span>

        {trend.trend !== "insufficient_data" && (
          <div className="card-grid" style={{ marginTop: 20 }}>
            <div>
              <div className="stat-label">Recent Avg Heart Rate</div>
              <div className="stat-value">{trend.avg_heart_rate_recent}<span className="stat-unit">bpm</span></div>
            </div>
            <div>
              <div className="stat-label">Previous Avg Heart Rate</div>
              <div className="stat-value">{trend.avg_heart_rate_previous}<span className="stat-unit">bpm</span></div>
            </div>
          </div>
        )}
        <p style={{ color: "#5C6E71", fontSize: 13, marginTop: 16 }}>{trend.note || trend.message}</p>
      </div>
    </Layout>
  );
}
```

### Step 43: Weekly Report page

Create `src/pages/Reports.js`:

```javascript
import { useEffect, useState } from "react";
import api from "../api";
import Layout from "../components/Layout";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";

export default function Reports() {
  const [weeks, setWeeks] = useState([]);

  useEffect(() => {
    api.get("/vitals/weekly-report/").then((res) => {
      const formatted = res.data.map((w) => ({
        ...w,
        weekLabel: new Date(w.week).toLocaleDateString([], { month: "short", day: "numeric" }),
      }));
      setWeeks(formatted.reverse());
    });
  }, []);

  return (
    <Layout>
      <div className="page-header">
        <h1>Weekly Report</h1>
        <p>Aggregated vitals and alert counts by week</p>
      </div>

      <div className="card">
        <h3>Average Heart Rate per Week</h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={weeks}>
            <CartesianGrid stroke="#E1E7E8" strokeDasharray="3 3" />
            <XAxis dataKey="weekLabel" fontSize={12} />
            <YAxis fontSize={12} />
            <Tooltip />
            <Bar dataKey="avg_heart_rate" fill="#0B5D6B" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <h3>Alerts per Week</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={weeks}>
            <CartesianGrid stroke="#E1E7E8" strokeDasharray="3 3" />
            <XAxis dataKey="weekLabel" fontSize={12} />
            <YAxis fontSize={12} allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="alert_count" fill="#C1443C" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <h3>Summary Table</h3>
        <table>
          <thead>
            <tr><th>Week</th><th>Avg HR</th><th>Max HR</th><th>Min HR</th><th>Avg SpO₂</th><th>Readings</th><th>Alerts</th></tr>
          </thead>
          <tbody>
            {weeks.map((w, i) => (
              <tr key={i}>
                <td>{w.weekLabel}</td>
                <td>{w.avg_heart_rate ?? "—"}</td>
                <td>{w.max_heart_rate ?? "—"}</td>
                <td>{w.min_heart_rate ?? "—"}</td>
                <td>{w.avg_spo2 ?? "—"}</td>
                <td>{w.reading_count}</td>
                <td>{w.alert_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
```

### Step 44: Final App.js with all routes

Replace `src/App.js`:

```javascript
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "./styles.css";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import Alerts from "./pages/Alerts";
import Trend from "./pages/Trend";
import Reports from "./pages/Reports";

function PrivateRoute({ children }) {
  const isLoggedIn = !!localStorage.getItem("access_token");
  return isLoggedIn ? children : <Navigate to="/login" />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
        <Route path="/history" element={<PrivateRoute><History /></PrivateRoute>} />
        <Route path="/alerts" element={<PrivateRoute><Alerts /></PrivateRoute>} />
        <Route path="/trend" element={<PrivateRoute><Trend /></PrivateRoute>} />
        <Route path="/reports" element={<PrivateRoute><Reports /></PrivateRoute>} />
        <Route path="/" element={<Navigate to="/dashboard" />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
```

### Step 45: Run it

```powershell
npm start
```

You now have 5 fully working pages, all pulling live data from your real Django backend:
**Live Status**, **History**, **Alerts & Map**, **Health Trend**, **Weekly Report** —
all sharing one consistent design system.

---

## What's still a placeholder (and where it plugs in later)

| Feature | Current state | Swap in later at... |
|---|---|---|
| Risk classification | Rule-based (`risk_engine.py`) | `predict_risk()` — Step 23 in main guide, once Random Forest is trained |
| Health Trend page | Rule-based heuristic (`TrendView`) | Same function body, once LSTM is trained |
| Alert map pins | Empty until lat/lng exists on alerts | Android app sends GPS on emergency (Step 48 in main guide) |
| SMS notification | Not built yet | Add to `alerts/utils.py` `send_notification()` |

Test each new page by generating a few readings first (via PowerShell or your simulator script)
so History, Trend, and Reports have data to show — an empty dashboard is hard to judge visually.
