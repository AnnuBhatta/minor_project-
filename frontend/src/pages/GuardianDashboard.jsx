import Layout from "../components/Layout";
import PatientManager from "../components/PatientManager";
import LiveAlertsPanel from "../components/GuardianDashboard";

export default function GuardianDashboard() {
  return (
    <Layout>
      <div className="page-header">
        <h1>My Patients</h1>
        <p>Patients you've approved to monitor</p>
      </div>

      <PatientManager />

      <LiveAlertsPanel />

      <div className="card" style={{ marginTop: 16 }}>
        <div className="stat-label" style={{ marginBottom: 8, fontSize: 15 }}>
          About emergency alerts
        </div>
        <p style={{ margin: 0, color: "var(--color-text-muted)" }}>
          You'll only receive alerts for patients whose requests you've approved. When one of them
          triggers an emergency, you'll get a push notification and a live alert with their name and
          location.
        </p>
      </div>
    </Layout>
  );
}
