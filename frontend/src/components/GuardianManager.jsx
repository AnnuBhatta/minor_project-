import { useCallback, useEffect, useState } from "react";
import { usePatient } from "../contexts/PatientContext";

const authHeaders = () => ({
  "Content-Type": "application/json",
  Authorization: `Bearer ${localStorage.getItem("access_token")}`,
});

export default function GuardianManager() {
  const { currentUser } = usePatient();
  const [guardians, setGuardians] = useState([]);
  const [requests, setRequests] = useState([]);
  const [query, setQuery] = useState("");
  const [note, setNote] = useState("");
  const [results, setResults] = useState([]);
  const [searched, setSearched] = useState(false);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState("");

  const showMessage = (text) => {
    setMessage(text);
    setError("");
  };
  const showError = (text) => {
    setError(text);
    setMessage("");
  };

  const fetchData = useCallback(async () => {
    try {
      const [gRes, rRes] = await Promise.all([
        fetch("/api/auth/my-guardians/", { headers: authHeaders() }),
        fetch("/api/auth/my-requests/", { headers: authHeaders() }),
      ]);
      const gData = await gRes.json();
      const rData = await rRes.json();
      if (!gRes.ok) throw new Error(gData.error || "Failed to load guardians");
      if (!rRes.ok) throw new Error(rData.error || "Failed to load requests");
      setGuardians(gData.guardians || []);
      setRequests(rData.requests || []);
    } catch (err) {
      showError(err.message || "Could not load your guardians");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const searchGuardians = async (e) => {
    e.preventDefault();
    const q = query.trim();
    if (q.length < 2) {
      showError("Enter at least 2 characters to search.");
      return;
    }
    setSearching(true);
    setSearched(true);
    setError("");
    setMessage("");
    try {
      const res = await fetch(`/api/auth/search-guardians/?q=${encodeURIComponent(q)}`, {
        headers: authHeaders(),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Search failed");
      setResults(Array.isArray(data) ? data : data.results || []);
    } catch (err) {
      showError(err.message || "Search failed");
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const sendRequest = async (guardianId, name) => {
    setBusy(true);
    try {
      const res = await fetch("/api/auth/send-request/", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ guardian_id: guardianId, message: note.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        showError(data.error || data.message || "Could not send request");
        return;
      }
      showMessage(data.message || "Request sent");
      setResults((prev) => prev.filter((g) => String(g.id) !== String(guardianId)));
      setNote("");
      await fetchData();
    } catch (err) {
      showError(err.message || "Could not send request");
    } finally {
      setBusy(false);
    }
  };

  const removeGuardian = async (guardianId, name) => {
    if (!window.confirm(`Remove ${name} from your guardians?`)) return;
    setBusy(true);
    try {
      const res = await fetch("/api/auth/remove-guardian/", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ guardian_id: guardianId }),
      });
      const data = await res.json();
      if (!res.ok) {
        showError(data.error || data.message || "Failed to remove guardian");
        return;
      }
      showMessage(data.message || "Guardian removed");
      await fetchData();
    } catch (err) {
      showError(err.message || "Could not remove guardian");
    } finally {
      setBusy(false);
    }
  };

  const pendingOutgoing = requests.filter(
    (r) => !r.incoming && r.status === "pending",
  );

  return (
    <>
      {message && <div className="flash flash-success">{message}</div>}
      {error && <div className="flash flash-error">{error}</div>}

      {loading ? (
        <div className="card">
          <p style={{ color: "var(--color-text-muted)" }}>Loading…</p>
        </div>
      ) : currentUser?.is_guardian ? (
        <div className="card">
          <h3 style={{ margin: 0, marginBottom: 12 }}>Guardian Management</h3>
          <p style={{ color: "var(--color-text-muted)" }}>
            You are logged in as a Guardian account. To search for guardians and
            send them monitoring requests, please log out and log in with your
            Patient account instead.
          </p>
        </div>
      ) : (
        <>
          <div className="card">
            <div
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}
            >
              <h3 style={{ margin: 0 }}>My Guardians</h3>
              <span className="stat-label" style={{ margin: 0 }}>
                {guardians.length} linked
              </span>
            </div>

            {guardians.length === 0 ? (
              <p style={{ color: "var(--color-text-muted)" }}>
                No guardians linked yet. Search below and send a request — they'll receive your
                emergency alerts once they approve.
              </p>
            ) : (
              <ul className="person-list">
                {guardians.map((g) => (
                  <li key={g.id}>
                    <div className="person-avatar">{g.full_name?.[0] || g.username?.[0] || "?"}</div>
                    <div className="person-info">
                      <div className="person-name">{g.full_name || g.username}</div>
                      <div className="person-sub">{g.email}</div>
                      {g.phone && <div className="person-sub">{g.phone}</div>}
                    </div>
                    <button
                      type="button"
                      className="btn-remove"
                      onClick={() => removeGuardian(g.id, g.full_name || g.username)}
                      disabled={busy}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card">
            <h3 style={{ margin: 0, marginBottom: 16 }}>Pending Requests</h3>
            {pendingOutgoing.length === 0 ? (
              <p style={{ color: "var(--color-text-muted)" }}>
                No pending requests. Guardians you've asked to monitor you will appear here.
              </p>
            ) : (
              <ul className="person-list">
                {pendingOutgoing.map((r) => (
                  <li key={r.id}>
                    <div className="person-avatar">{r.guardian.full_name?.[0] || "?"}</div>
                    <div className="person-info">
                      <div className="person-name">{r.guardian.full_name || r.guardian.username}</div>
                      <div className="person-sub">{r.guardian.email}</div>
                      {r.message && <div className="person-sub">Note: {r.message}</div>}
                    </div>
                    <span className="status-chip pending">Pending</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card">
            <h3 style={{ margin: 0, marginBottom: 16 }}>Find a Guardian</h3>
            <form className="search-row" onSubmit={searchGuardians}>
              <input
                type="text"
                placeholder="Search by name or email…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                minLength={2}
                required
              />
              <button type="submit" className="btn-add" disabled={searching}>
                {searching ? "Searching…" : "Search"}
              </button>
            </form>
            <input
              type="text"
              className="search-note"
              placeholder="Add an optional message for the guardian…"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              disabled={searching}
            />

            {searched && !searching && results.length === 0 && (
              <p style={{ color: "var(--color-text-muted)" }}>
                No guardians found. Only registered guardians who haven't already been requested
                appear in results.
              </p>
            )}

            <ul className="person-list">
              {results.map((g) => (
                <li key={g.id}>
                  <div className="person-avatar">{g.full_name?.[0] || g.username?.[0] || "?"}</div>
                  <div className="person-info">
                    <div className="person-name">{g.full_name || g.username}</div>
                    <div className="person-sub">{g.email}</div>
                    {g.phone && <div className="person-sub">{g.phone}</div>}
                  </div>
                  <button
                    type="button"
                    className="btn-add"
                    onClick={() => sendRequest(g.id, g.full_name || g.username)}
                    disabled={busy}
                  >
                    {busy ? "Sending…" : "Request"}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </>
  );
}