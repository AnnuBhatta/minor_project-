import React, { useState } from "react";
import AlertNotifications from "./AlertNotifications";
import DemoControls from "./DemoControls";
import TurboDemoControls from "./TurboDemoControls";

const PatientDashboard = () => {
  const [creatingEmergency, setCreatingEmergency] = useState(false);

  const user = React.useMemo(() => {
    try {
      const userData = localStorage.getItem("user");
      return userData ? JSON.parse(userData) : null;
    } catch {
      return null;
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user");
    window.location.href = "/login";
  };

  const triggerEmergency = async () => {
    try {
      setCreatingEmergency(true);

      if (!navigator.geolocation) {
        alert("Geolocation is not supported by your browser");
        setCreatingEmergency(false);
        return;
      }

      const position = await new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 10000,
        });
      });

      const token = localStorage.getItem("access_token");
      if (!token) {
        alert("Please login first");
        setCreatingEmergency(false);
        return;
      }

      const emergencyData = {
        location: {
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        },
        severity: "critical",
        description: "Emergency triggered by user",
        is_manual: true,
      };

      const response = await fetch("/api/emergency/events/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(emergencyData),
      });

      if (response.ok) {
        const data = await response.json();
        window.location.href = `/emergency/${data.id}`;
      } else {
        alert("Failed to trigger emergency. Please try again.");
      }
    } catch (error) {
      console.error("Error triggering emergency:", error);
      alert("Failed to trigger emergency. Please try again.");
    } finally {
      setCreatingEmergency(false);
    }
  };

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>🏥 Health Monitor</h1>
        <div className="user-info">
          <span>Welcome, {user?.first_name || user?.username || "User"}!</span>
          <button onClick={handleLogout} className="logout-btn">
            Logout
          </button>
        </div>
      </header>

      <div className="dashboard-content">
        <div className="emergency-section">
          <h2>Emergency</h2>
          <button
            className="emergency-button"
            onClick={triggerEmergency}
            disabled={creatingEmergency}
          >
            {creatingEmergency
              ? "🚨 Creating Emergency..."
              : "🚨 Trigger Emergency"}
          </button>
          <p className="emergency-note">
            ⚠️ Click this button only in case of a real emergency
          </p>
        </div>

        <div className="alerts-section-wrapper">
          <AlertNotifications userId={user?.id} />
        </div>

        <div className="quick-actions">
          <h2>Quick Actions</h2>
          <div className="action-grid">
            <div
              className="action-card"
              onClick={() => (window.location.href = "/vitals")}
            >
              <h3>📊 View Vitals</h3>
              <p>Check your latest health vitals</p>
            </div>
            <div
              className="action-card"
              onClick={() => (window.location.href = "/history")}
            >
              <h3>📋 History</h3>
              <p>View your health history</p>
            </div>
            <div
              className="action-card"
              onClick={() => (window.location.href = "/profile")}
            >
              <h3>⚙️ Settings</h3>
              <p>Manage your profile and preferences</p>
            </div>
          </div>
        </div>

        <div className="demo-section">
          <DemoControls />
          <div style={{ marginTop: 20 }}>
            <TurboDemoControls />
          </div>
        </div>
      </div>

      <style>{`
        .dashboard-container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 20px;
          font-family: Arial, sans-serif;
          background: #f5f7fa;
          min-height: 100vh;
        }

        .dashboard-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px 30px;
          background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%);
          color: white;
          border-radius: 12px;
          margin-bottom: 30px;
          flex-wrap: wrap;
          gap: 10px;
        }

        .dashboard-header h1 {
          margin: 0;
          font-size: 24px;
        }

        .user-info {
          display: flex;
          align-items: center;
          gap: 15px;
        }

        .logout-btn {
          padding: 8px 20px;
          background: rgba(255,255,255,0.15);
          border: 1px solid rgba(255,255,255,0.3);
          border-radius: 6px;
          color: white;
          cursor: pointer;
          transition: all 0.3s;
        }

        .logout-btn:hover {
          background: rgba(255,255,255,0.25);
        }

        .dashboard-content {
          display: grid;
          gap: 30px;
        }

        .emergency-section {
          background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
          padding: 30px;
          border-radius: 12px;
          text-align: center;
          border: 2px solid #ff9800;
        }

        .emergency-section h2 {
          color: #e65100;
          margin-top: 0;
        }

        .emergency-button {
          background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
          color: white;
          border: none;
          padding: 20px 50px;
          border-radius: 10px;
          font-size: 24px;
          font-weight: bold;
          cursor: pointer;
          transition: all 0.3s;
          animation: pulse 2s infinite;
          box-shadow: 0 4px 15px rgba(244, 67, 54, 0.5);
        }

        .emergency-button:hover:not(:disabled) {
          transform: scale(1.05);
          box-shadow: 0 6px 25px rgba(244, 67, 54, 0.6);
        }

        .emergency-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
          animation: none;
        }

        @keyframes pulse {
          0% { box-shadow: 0 0 0 0 rgba(244, 67, 54, 0.4); }
          70% { box-shadow: 0 0 0 20px rgba(244, 67, 54, 0); }
          100% { box-shadow: 0 0 0 0 rgba(244, 67, 54, 0); }
        }

        .emergency-note {
          color: #666;
          margin-top: 15px;
          font-size: 14px;
        }

        .alerts-section-wrapper {
          background: white;
          border-radius: 12px;
          padding: 20px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        .quick-actions {
          background: white;
          padding: 25px;
          border-radius: 12px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        .quick-actions h2 {
          color: #333;
          margin-top: 0;
          margin-bottom: 20px;
          font-size: 20px;
        }

        .action-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 20px;
        }

        .action-card {
          background: #f8f9fa;
          padding: 20px;
          border-radius: 10px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.06);
          transition: all 0.3s;
          cursor: pointer;
          border: 2px solid transparent;
        }

        .action-card:hover {
          transform: translateY(-5px);
          box-shadow: 0 6px 20px rgba(0,0,0,0.1);
          border-color: #1976d2;
          background: white;
        }

        .action-card h3 {
          margin: 0 0 8px 0;
          color: #1976d2;
          font-size: 18px;
        }

        .action-card p {
          margin: 0;
          color: #666;
          font-size: 14px;
        }

        .demo-section {
          background: white;
          padding: 25px;
          border-radius: 12px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        @media (max-width: 768px) {
          .dashboard-container {
            padding: 12px;
          }

          .dashboard-header {
            flex-direction: column;
            text-align: center;
            padding: 15px 20px;
          }

          .user-info {
            flex-direction: column;
            width: 100%;
          }

          .user-info span {
            width: 100%;
            text-align: center;
          }

          .logout-btn {
            width: 100%;
          }

          .emergency-button {
            font-size: 18px;
            padding: 15px 30px;
          }

          .action-grid {
            grid-template-columns: 1fr;
          }
        }

        @media (min-width: 769px) and (max-width: 1024px) {
          .action-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }
      `}</style>
    </div>
  );
};

export default PatientDashboard;
