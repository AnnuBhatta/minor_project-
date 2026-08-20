import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const EMPTY_FORM = {
  username: "",
  email: "",
  first_name: "",
  last_name: "",
  phone: "",
  password: "",
  confirmPassword: "",
  emergency_contact_name: "",
  emergency_contact_phone: "",
  emergency_contact_email: "",
};

export default function Register() {
  const [role, setRole] = useState("patient");
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const isGuardian = role === "guardian";

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const firstError = (data) => {
    const values = data && typeof data === "object" ? Object.values(data) : [];
    for (const value of values) {
      if (Array.isArray(value) && value.length) return value[0];
      if (typeof value === "string") return value;
    }
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    const { username, email, password, confirmPassword } = form;
    if (!username || !email || !password || !confirmPassword) {
      setError("Please fill in all required fields.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    const payload = {
      username,
      email,
      password,
      password2: confirmPassword,
      first_name: form.first_name || "",
      last_name: form.last_name || "",
      phone: form.phone || "",
      is_guardian: isGuardian,
    };

    if (isGuardian) {
      payload.emergency_contact_name = form.emergency_contact_name || "";
      payload.emergency_contact_phone = form.emergency_contact_phone || "";
      payload.emergency_contact_email = form.emergency_contact_email || "";
    }

    setLoading(true);
    try {
      const res = await fetch("/api/auth/register/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(firstError(data) || "Registration failed. Please try again.");
      }

      localStorage.setItem("access_token", data.access);
      localStorage.setItem("refresh_token", data.refresh);
      localStorage.setItem("user", JSON.stringify(data.user));

      navigate(isGuardian ? "/guardian-dashboard" : "/patient-dashboard");
    } catch (err) {
      setError(err.message || "Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card wide">
        <div className="auth-brand">
          <div className="heart">♥</div>
          <h1>VitalWatch</h1>
          <p>Create your health monitoring account</p>
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
            <label htmlFor="reg-username">Username *</label>
            <input
              id="reg-username"
              name="username"
              type="text"
              value={form.username}
              onChange={handleChange}
              placeholder="Choose a username"
              required
              autoComplete="username"
            />
          </div>

          <div className="auth-field">
            <label htmlFor="reg-email">Email *</label>
            <input
              id="reg-email"
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              placeholder="you@example.com"
              required
              autoComplete="email"
            />
          </div>

          <div className="auth-grid-2">
            <div className="auth-field">
              <label htmlFor="reg-first">First name</label>
              <input
                id="reg-first"
                name="first_name"
                type="text"
                value={form.first_name}
                onChange={handleChange}
                placeholder="Optional"
              />
            </div>
            <div className="auth-field">
              <label htmlFor="reg-last">Last name</label>
              <input
                id="reg-last"
                name="last_name"
                type="text"
                value={form.last_name}
                onChange={handleChange}
                placeholder="Optional"
              />
            </div>
          </div>

          <div className="auth-field">
            <label htmlFor="reg-phone">Phone</label>
            <input
              id="reg-phone"
              name="phone"
              type="tel"
              value={form.phone}
              onChange={handleChange}
              placeholder="Optional"
              autoComplete="tel"
            />
          </div>

          <div className="auth-field">
            <label htmlFor="reg-password">Password *</label>
            <input
              id="reg-password"
              name="password"
              type="password"
              value={form.password}
              onChange={handleChange}
              placeholder="Min 8 characters"
              required
              autoComplete="new-password"
            />
          </div>

          <div className="auth-field">
            <label htmlFor="reg-confirm">Confirm password *</label>
            <input
              id="reg-confirm"
              name="confirmPassword"
              type="password"
              value={form.confirmPassword}
              onChange={handleChange}
              placeholder="Re-enter your password"
              required
              autoComplete="new-password"
            />
          </div>

          {isGuardian && (
            <>
              <div className="auth-section">Emergency contact (guardian)</div>
              <div className="auth-field">
                <label htmlFor="reg-ec-name">Emergency contact name</label>
                <input
                  id="reg-ec-name"
                  name="emergency_contact_name"
                  type="text"
                  value={form.emergency_contact_name}
                  onChange={handleChange}
                  placeholder="Optional"
                />
              </div>
              <div className="auth-field">
                <label htmlFor="reg-ec-phone">Emergency contact phone</label>
                <input
                  id="reg-ec-phone"
                  name="emergency_contact_phone"
                  type="tel"
                  value={form.emergency_contact_phone}
                  onChange={handleChange}
                  placeholder="Optional"
                />
              </div>
              <div className="auth-field">
                <label htmlFor="reg-ec-email">Emergency contact email</label>
                <input
                  id="reg-ec-email"
                  name="emergency_contact_email"
                  type="email"
                  value={form.emergency_contact_email}
                  onChange={handleChange}
                  placeholder="Optional"
                />
              </div>
            </>
          )}

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading
              ? "Creating account..."
              : `Register as ${isGuardian ? "Guardian" : "Patient"}`}
          </button>
        </form>

        <div className="auth-switch">
          Already have an account? <Link to="/login">Log in</Link>
        </div>
      </div>
    </div>
  );
}
