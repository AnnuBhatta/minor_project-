import React, { useState } from 'react';

const Register = () => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    password2: '',
    first_name: '',
    last_name: '',
    phone: '',
    is_guardian: false,
    emergency_contact_name: '',
    emergency_contact_phone: '',
    emergency_contact_email: ''
  });
  const [role, setRole] = useState('patient');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleRoleChange = (selectedRole) => {
    setRole(selectedRole);
    setFormData({
      ...formData,
      is_guardian: selectedRole === 'guardian'
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    if (formData.password !== formData.password2) {
      setError('Passwords do not match');
      return;
    }
    
    setLoading(true);

    try {
      const response = await fetch('/api/auth/register/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        setSuccess(true);
        setTimeout(() => {
          window.location.href = '/login';
        }, 2000);
      } else {
        const data = await response.json();
        setError(data.error || 'Registration failed');
      }
    } catch (error) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="register-container">
      <div className="register-box">
        <h1>🏥 Health Monitor</h1>
        <h2>Create Account</h2>
        
        {error && <div className="error-message">{error}</div>}
        {success && (
          <div className="success-message">
            ✅ Registration successful! Redirecting to login...
          </div>
        )}
        
        {/* Role Selection */}
        <div className="role-selector">
          <button 
            type="button"
            className={`role-btn ${role === 'patient' ? 'active' : ''}`}
            onClick={() => handleRoleChange('patient')}
          >
            👤 Patient
          </button>
          <button 
            type="button"
            className={`role-btn ${role === 'guardian' ? 'active' : ''}`}
            onClick={() => handleRoleChange('guardian')}
          >
            📱 Guardian
          </button>
        </div>
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Username *</label>
            <input
              name="username"
              value={formData.username}
              onChange={handleChange}
              required
              placeholder="Enter username"
            />
          </div>
          
          <div className="form-group">
            <label>Email *</label>
            <input
              name="email"
              type="email"
              value={formData.email}
              onChange={handleChange}
              required
              placeholder="your@email.com"
            />
          </div>
          
          <div className="form-row">
            <div className="form-group">
              <label>First Name</label>
              <input
                name="first_name"
                value={formData.first_name}
                onChange={handleChange}
                placeholder="John"
              />
            </div>
            <div className="form-group">
              <label>Last Name</label>
              <input
                name="last_name"
                value={formData.last_name}
                onChange={handleChange}
                placeholder="Doe"
              />
            </div>
          </div>
          
          <div className="form-group">
            <label>Phone</label>
            <input
              name="phone"
              value={formData.phone}
              onChange={handleChange}
              placeholder="+1234567890"
            />
          </div>
          
          <div className="form-row">
            <div className="form-group">
              <label>Password *</label>
              <input
                name="password"
                type="password"
                value={formData.password}
                onChange={handleChange}
                required
                placeholder="••••••••"
              />
            </div>
            <div className="form-group">
              <label>Confirm Password *</label>
              <input
                name="password2"
                type="password"
                value={formData.password2}
                onChange={handleChange}
                required
                placeholder="••••••••"
              />
            </div>
          </div>
          
          {/* Guardian specific fields */}
          {role === 'guardian' && (
            <div className="guardian-fields">
              <h3>📱 Guardian Information</h3>
              <div className="form-group">
                <label>Emergency Contact Name</label>
                <input
                  name="emergency_contact_name"
                  value={formData.emergency_contact_name}
                  onChange={handleChange}
                  placeholder="Contact person name"
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Emergency Contact Phone</label>
                  <input
                    name="emergency_contact_phone"
                    value={formData.emergency_contact_phone}
                    onChange={handleChange}
                    placeholder="+1234567890"
                  />
                </div>
                <div className="form-group">
                  <label>Emergency Contact Email</label>
                  <input
                    name="emergency_contact_email"
                    type="email"
                    value={formData.emergency_contact_email}
                    onChange={handleChange}
                    placeholder="contact@email.com"
                  />
                </div>
              </div>
            </div>
          )}
          
          <button type="submit" disabled={loading}>
            {loading ? 'Creating Account...' : `Register as ${role === 'patient' ? 'Patient' : 'Guardian'}`}
          </button>
        </form>
        
        <div className="login-link">
          Already have an account? <a href="/login">Login here</a>
        </div>
      </div>

      <style>{`
        .register-container {
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 100vh;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          font-family: Arial, sans-serif;
          padding: 20px;
        }

        .register-box {
          background: white;
          padding: 40px;
          border-radius: 12px;
          box-shadow: 0 10px 25px rgba(0,0,0,0.1);
          width: 100%;
          max-width: 500px;
          max-height: 90vh;
          overflow-y: auto;
        }

        .register-box::-webkit-scrollbar {
          width: 6px;
        }

        .register-box::-webkit-scrollbar-track {
          background: #f1f1f1;
          border-radius: 3px;
        }

        .register-box::-webkit-scrollbar-thumb {
          background: #c1c1c1;
          border-radius: 3px;
        }

        .register-box h1 {
          text-align: center;
          color: #1976d2;
          margin: 0 0 5px 0;
          font-size: 28px;
        }

        .register-box h2 {
          text-align: center;
          color: #333;
          margin: 0 0 25px 0;
          font-weight: normal;
          font-size: 20px;
        }

        .role-selector {
          display: flex;
          gap: 10px;
          margin-bottom: 25px;
        }

        .role-btn {
          flex: 1;
          padding: 12px;
          border: 2px solid #ddd;
          border-radius: 8px;
          background: white;
          cursor: pointer;
          font-size: 15px;
          font-weight: bold;
          transition: all 0.3s;
          color: #666;
        }

        .role-btn:hover {
          border-color: #1976d2;
          background: #f5f5f5;
        }

        .role-btn.active {
          border-color: #1976d2;
          background: #1976d2;
          color: white;
        }

        .form-group {
          margin-bottom: 15px;
        }

        .form-group label {
          display: block;
          margin-bottom: 5px;
          color: #333;
          font-weight: 500;
          font-size: 14px;
        }

        .form-group input {
          width: 100%;
          padding: 10px 12px;
          border: 1px solid #ddd;
          border-radius: 6px;
          font-size: 14px;
          box-sizing: border-box;
          transition: border-color 0.3s;
        }

        .form-group input:focus {
          outline: none;
          border-color: #1976d2;
          box-shadow: 0 0 0 3px rgba(25, 118, 210, 0.1);
        }

        .form-row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 15px;
        }

        .guardian-fields {
          background: #f0f7ff;
          padding: 20px;
          border-radius: 8px;
          margin: 15px 0 20px 0;
          border-left: 4px solid #1976d2;
        }

        .guardian-fields h3 {
          margin: 0 0 15px 0;
          color: #1976d2;
          font-size: 16px;
        }

        .error-message {
          background: #ffebee;
          color: #c62828;
          padding: 10px 15px;
          border-radius: 6px;
          margin-bottom: 15px;
          border-left: 4px solid #c62828;
          font-size: 14px;
        }

        .success-message {
          background: #e8f5e9;
          color: #2e7d32;
          padding: 10px 15px;
          border-radius: 6px;
          margin-bottom: 15px;
          border-left: 4px solid #2e7d32;
          font-size: 14px;
        }

        button[type="submit"] {
          width: 100%;
          padding: 14px;
          background: #1976d2;
          color: white;
          border: none;
          border-radius: 6px;
          font-size: 16px;
          font-weight: bold;
          cursor: pointer;
          transition: all 0.3s;
          margin-top: 10px;
        }

        button[type="submit"]:hover:not(:disabled) {
          background: #1565c0;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(25, 118, 210, 0.3);
        }

        button[type="submit"]:disabled {
          opacity: 0.6;
          cursor: not-allowed;
          transform: none;
        }

        .login-link {
          margin-top: 20px;
          text-align: center;
          color: #666;
          font-size: 14px;
        }

        .login-link a {
          color: #1976d2;
          text-decoration: none;
          font-weight: 500;
        }

        .login-link a:hover {
          text-decoration: underline;
        }

        @media (max-width: 768px) {
          .register-box {
            padding: 25px;
          }

          .form-row {
            grid-template-columns: 1fr;
            gap: 0;
          }

          .role-selector {
            flex-direction: column;
          }

          .role-btn {
            padding: 15px;
          }

          .register-box h1 {
            font-size: 24px;
          }
        }
      `}</style>
    </div>
  );
};

export default Register;