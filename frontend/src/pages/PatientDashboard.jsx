import { Link } from "react-router-dom";
import Layout from "../components/Layout";
import GuardianManager from "../components/GuardianManager";
import DemoControls from "../components/DemoControls";
import TurboDemoControls from "../components/TurboDemoControls";
import LocationReporter from "../components/LocationReporter";

export default function PatientDashboard() {
  return (
    <Layout>
      <div className="page-header">
        <h1>My Guardians</h1>
        <p>Manage who receives your emergency alerts</p>
      </div>

      <LocationReporter />

      <DemoControls />

      <TurboDemoControls />

      <GuardianManager />

      <div className="card" style={{ marginTop: 16 }}>
        <div className="stat-label" style={{ marginBottom: 8, fontSize: 15 }}>
          View your live vitals
        </div>
        <p style={{ margin: 0, color: "var(--color-text-muted)" }}>
          See your real-time heart rate, SpO₂, blood pressure and health risk, plus run demo
          scenarios to test the alert system.
        </p>
        <Link to="/live-status" className="btn-link">
          Open live dashboard →
        </Link>
      </div>
    </Layout>
  );
}
