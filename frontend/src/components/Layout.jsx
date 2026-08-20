import { NavLink, useNavigate } from 'react-router-dom';

export default function Layout({ children }) {
  const navigate = useNavigate();

  const logout = () => {
    localStorage.removeItem('access_token');
    navigate('/login');
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span style={{ color: '#2FA8A0', fontSize: 20 }}>♥</span> VitalWatch
        </div>
        <NavLink to="/live-status" className={({ isActive }) => (isActive ? 'active' : '')}>
          Live Status
        </NavLink>
        <NavLink to="/history" className={({ isActive }) => (isActive ? 'active' : '')}>
          History
        </NavLink>
        <NavLink to="/alerts" className={({ isActive }) => (isActive ? 'active' : '')}>
          Alerts & Map
        </NavLink>
        <NavLink to="/trend" className={({ isActive }) => (isActive ? 'active' : '')}>
          Health Trend
        </NavLink>
        <NavLink to="/reports" className={({ isActive }) => (isActive ? 'active' : '')}>
          Weekly Report
        </NavLink>
        <div style={{ flex: 1 }} />
        <a onClick={logout} style={{ cursor: 'pointer' }}>
          Log out
        </a>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}
