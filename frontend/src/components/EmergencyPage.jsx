import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import EmergencyDashboard from '../components/EmergencyDashboard';

const EmergencyPage = () => {
  const { emergencyId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Check if user is authenticated
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      navigate('/login');
      return;
    }
    setLoading(false);
  }, [navigate]);

  if (loading) {
    return (
      <div className="loading-container">
        <p>Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-container">
        <h2>⚠️ Error</h2>
        <p>{error}</p>
        <button onClick={() => navigate('/live-status')}>Go to Dashboard</button>
      </div>
    );
  }

  return (
    <div className="emergency-page">
      <EmergencyDashboard emergencyEventId={parseInt(emergencyId)} />
    </div>
  );
};

export default EmergencyPage;