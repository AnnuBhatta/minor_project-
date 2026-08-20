import { useState } from "react";
import { Link } from "react-router-dom";

export default function Login() {
  const [role, setRole] = useState("patient");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/auth/login/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(
          data?.non_field_errors?.[0] ||
            data?.error ||
            "Invalid username or password"
        );
      }

      localStorage.setItem("access_token", data.access);
      localStorage.setItem("refresh_token", data.refresh);
      localStorage.setItem("user", JSON.stringify(data.user));

      const isGuardian = Boolean(data.user.is_guardian);
      // Full page redirect (not SPA navigate) so every provider re-reads the
      // new account from localStorage. Without this, PatientContext keeps the
      // PREVIOUS session's user in memory — e.g. switching from a guardian to
      // a patient account still shows the guardian UI.
      if (role === "guardian" && isGuardian) {
        window.location.href = "/guardian-dashboard";
      } else if (role === "patient" && !isGuardian) {
        window.location.href = "/patient-dashboard";
      } else {
        setError(
          isGuardian
            ? "This account is a Guardian. Select Guardian to log in."
            : "This account is a Patient. Select Patient to log in."
        );
      }
    } catch (err) {
      setError(err.message || "Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="heart">♥</div>
          <h1>VitalWatch</h1>
          <p>Sign in to your health monitoring dashboard</p>
        </div>

        {error && <div className="auth-error">{error}</div>}

        <div className="auth-role-group" role="tablist" aria-label="Account role">
          <button
            type="button"
            className={`auth-role-btn ${role === "patient" ? "active" : ""}`}
            onClick={() => setRole("patient")}
          >
            👤 Patient
          </button>
          <button
            type="button"
            className={`auth-role-btn ${role === "guardian" ? "active" : ""}`}
            onClick={() => setRole("guardian")}
          >
            📱 Guardian
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="auth-field">
            <label htmlFor="login-username">Username or email</label>
            <input
              id="login-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username or email"
              required
              autoComplete="username"
            />
          </div>

          <div className="auth-field">
            <label htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
              autoComplete="current-password"
            />
          </div>

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading
              ? "Logging in..."
              : `Login as ${role === "patient" ? "Patient" : "Guardian"}`}
          </button>
        </form>

        <div className="auth-switch">
          Don't have an account? <Link to="/register">Register here</Link>
        </div>
      </div>
    </div>
  );
}
