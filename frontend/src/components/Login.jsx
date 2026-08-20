import React, { useState } from 'react';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('patient'); // 'patient' or 'guardian'
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch('/api/auth/login/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username, password })
      });

      if (response.ok) {
        const data = await response.json();
        localStorage.setItem('access_token', data.access);
        localStorage.setItem('refresh_token', data.refresh);
        localStorage.setItem('user', JSON.stringify(data.user));
        
        // Redirect based on role
        if (role === 'guardian' && data.user.is_guardian) {
          window.location.href = '/guardian-dashboard';
        } else if (role === 'patient' && !data.user.is_guardian) {
          window.location.href = '/patient-dashboard';
        } else {
          setError('Invalid role selected for this account');
        }
      } else {
        const data = await response.json();
        setError(data.error || 'Invalid credentials');
      }
    } catch (error) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>🏥 Health Monitor</h1>
        <h2>Login</h2>
        
        {error && <div className="error-message">{error}</div>}
        
        <div className="role-selector">
          <button 
            className={`role-btn ${role === 'patient' ? 'active' : ''}`}
            onClick={() => setRole('patient')}
          >
            👤 Patient
          </button>
          <button 
            className={`role-btn ${role === 'guardian' ? 'active' : ''}`}
            onClick={() => setRole('guardian')}
          >
            📱 Guardian
          </button>
        </div>
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Username or Email</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              placeholder="Enter your username"
            />
          </div>
          
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Enter your password"
            />
          </div>
          
          <button type="submit" disabled={loading}>
            {loading ? 'Logging in...' : `Login as ${role === 'patient' ? 'Patient' : 'Guardian'}`}
          </button>
        </form>
        
        <div className="register-link">
          Don't have an account? <a href="/register">Register here</a>
        </div>
      </div>

      <style>{`
        .login-container {
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 100vh;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          font-family: Arial, sans-serif;
        }

        .login-box {
          background: white;
          padding: 40px;
          border-radius: 10px;
          box-shadow: 0 10px 25px rgba(0,0,0,0.1);
          width: 100%;
          max-width: 400px;
        }

        .login-box h1 {
          text-align: center;
          color: #1976d2;
          margin: 0 0 5px 0;
        }

        .login-box h2 {
          text-align: center;
          color: #333;
          margin: 0 0 20px 0;
          font-weight: normal;
        }

        .role-selector {
          display: flex;
          gap: 10px;
          margin-bottom: 20px;
        }

        .role-btn {
          flex: 1;
          padding: 10px;
          border: 2px solid #ddd;
          border-radius: 8px;
          background: white;
          cursor: pointer;
          font-size: 14px;
          font-weight: bold;
          transition: all 0.3s;
          color: #666;
        }

        .role-btn:hover {
          border-color: #1976d2;
        }

        .role-btn.active {
          border-color: #1976d2;
          background: #1976d2;
          color: white;
        }

        .form-group {
          margin-bottom: 20px;
        }

        .form-group label {
          display: block;
          margin-bottom: 5px;
          color: #333;
          font-weight: 500;
        }

        .form-group input {
          width: 100%;
          padding: 10px;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 16px;
          box-sizing: border-box;
          transition: border-color 0.3s;
        }

        .form-group input:focus {
          outline: none;
          border-color: #1976d2;
        }

        .error-message {
          background: #ffebee;
          color: #c62828;
          padding: 10px;
          border-radius: 4px;
          margin-bottom: 15px;
          border-left: 4px solid #c62828;
        }

        button[type="submit"] {
          width: 100%;
          padding: 12px;
          background: #1976d2;
          color: white;
          border: none;
          border-radius: 4px;
          font-size: 16px;
          font-weight: bold;
          cursor: pointer;
          transition: background 0.3s;
        }

        button[type="submit"]:hover:not(:disabled) {
          background: #1565c0;
        }

        button[type="submit"]:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .register-link {
          margin-top: 15px;
          text-align: center;
          color: #666;
        }

        .register-link a {
          color: #1976d2;
          text-decoration: none;
        }

        .register-link a:hover {
          text-decoration: underline;
        }
      `}</style>
    </div>
  );
};

export default Login;