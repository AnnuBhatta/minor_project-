import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import EmergencyDashboard from "../components/EmergencyDashboard";

const EmergencyPage = () => {
  const { emergencyId } = useParams();
  const navigate = useNavigate();

  // Check if authenticated
  const token = localStorage.getItem("access_token");
  if (!token) {
    navigate("/login");
    return null;
  }

  return (
    <div className="emergency-page">
      <EmergencyDashboard emergencyEventId={parseInt(emergencyId)} />
    </div>
  );
};

export default EmergencyPage;
