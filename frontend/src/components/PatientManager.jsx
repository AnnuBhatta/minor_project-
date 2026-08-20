import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const authHeaders = () => ({
  "Content-Type": "application/json",
  Authorization: `Bearer ${localStorage.getItem("access_token")}`,
});

export default function PatientManager() {
  const [patients, setPatients] = useState([]);
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState(null);
  const navigate = useNavigate();

  const fetchData = useCallback(async () => {
    try {
      const [pRes, rRes] = await Promise.all([
        fetch("/api/auth/my-patients/", { headers: authHeaders() }),
        fetch("/api/auth/my-requests/", { headers: authHeaders() }),
      ]);
      const pData = await pRes.json();
      const rData = await rRes.json();
      if (!pRes.ok) throw new Error(pData.error || "Failed to load patients");
      if (!rRes.ok) throw new Error(rData.error || "Failed to load requests");
      setPatients(pData.patients || []);
      setRequests(rData.requests || []);
    } catch (err) {
      setError(err.message || "Could not load your patients");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const respond = async (id, action, name) => {
    setBusy(true);
    setError("");
    setMessage(null);
    try {
      const res = await fetch(`/api/auth/${action}-request/${id}/`, {
        method: "POST",
        headers: authHeaders(),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || data.message || `Could not ${action} the request`);
        return;
      }
      setMessage(data.message || `Request ${action === "approve" ? "approved" : "rejected"}`);
      await fetchData();
    } catch (err) {
      setError(err.message || `Could not ${action} the request`);
    } finally {
      setBusy(false);
    }
  };

  const openPatient = (patient) => {
    localStorage.setItem("selected_patient_id", String(patient.id));
    navigate("/live-status");
  };

  const pendingIncoming = requests.filter(
    (r) => r.incoming && r.status === "pending",
  );

  return (
    <>
      {message && <div className="flash flash-success">{message}</div>}
      {error && <div className="flash flash-error">{error}</div>}

      {loading ? (
        <div className="card">
          <p style={{ color: "var(--color-text-muted)" }}>Loading…</p>
        </div>
      ) : (
        <>
          <div className="card">
            <div
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}
            >
              <h3 style={{ margin: 0 }}>Pending Requests</h3>
              <span className="stat-label" style={{ margin: 0 }}>
                {pendingIncoming.length} awaiting your approval
              </span>
            </div>

            {pendingIncoming.length === 0 ? (
              <p style={{ color: "var(--color-text-muted)" }}>
                No pending requests. When a patient asks you to monitor them, their request will
                appear here for your approval.
              </p>
            ) : (
              <ul className="person-list">
                {pendingIncoming.map((r) => (
                  <li key={r.id}>
                    <div className="person-avatar">{r.patient.full_name?.[0] || "?"}</div>
                    <div className="person-info">
                      <div className="person-name">{r.patient.full_name || r.patient.username}</div>
                      <div className="person-sub">{r.patient.email}</div>
                      {r.patient.phone && <div className="person-sub">{r.patient.phone}</div>}
                      {r.message && <div className="person-sub">Note: {r.message}</div>}
                    </div>
                    <div className="action-stack">
                      <button
                        type="button"
                        className="btn-add"
                        onClick={() => respond(r.id, "approve", r.patient.full_name)}
                        disabled={busy}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="btn-remove"
                        onClick={() => respond(r.id, "reject", r.patient.full_name)}
                        disabled={busy}
                      >
                        Reject
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card">
            <div
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}
            >
              <h3 style={{ margin: 0 }}>My Patients</h3>
              <span className="stat-label" style={{ margin: 0 }}>
                {patients.length} monitored
              </span>
            </div>

            {patients.length === 0 ? (
              <p style={{ color: "var(--color-text-muted)" }}>
                You're not monitoring any patients yet. Approve a request above and the patient will
                appear here.
              </p>
            ) : (
              <ul className="person-list">
                {patients.map((p) => (
                  <li
                    key={p.id}
                    className="patient-row"
                    onClick={() => openPatient(p)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === "Enter" && openPatient(p)}
                  >
                    <div className="person-avatar">{p.full_name?.[0] || p.username?.[0] || "?"}</div>
                    <div className="person-info">
                      <div className="person-name">{p.full_name || p.username}</div>
                      <div className="person-sub">{p.email}</div>
                      {p.phone && <div className="person-sub">{p.phone}</div>}
                    </div>
                    <span className={`status-pill ${p.is_online ? "online" : "offline"}`}>
                      {p.is_online ? "● Online" : "○ Offline"}
                    </span>
                  </li>
                ))}
              </ul>
            )}

            <p className="hint">Click a patient to open their live vitals and alerts.</p>
          </div>
        </>
      )}
    </>
  );
}