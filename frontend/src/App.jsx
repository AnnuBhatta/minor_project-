import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Login from "./pages/Login";
import Register from "./pages/Register";
import LiveStatus from "./pages/LiveStatus";
import PatientDashboard from "./pages/PatientDashboard";
import GuardianDashboard from "./pages/GuardianDashboard";
import History from "./pages/History";
import Alerts from "./pages/Alerts";
import Trend from "./pages/Trend";
import Reports from "./pages/Reports";

import { PatientProvider } from "./contexts/PatientContext";
import { WebSocketProvider } from "./contexts/WebSocketContext";
import FcmRegistration from "./components/FcmRegistration";

function RequireAuth({ children }) {
  if (!localStorage.getItem("access_token")) {
    return <Navigate to="/login" replace />;
  }
  return (
    <>
      <FcmRegistration />
      {children}
    </>
  );
}

export default function App() {
  return (
    <PatientProvider>
      <WebSocketProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Navigate to="/login" replace />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            <Route
              path="/patient-dashboard"
              element={
                <RequireAuth>
                  <PatientDashboard />
                </RequireAuth>
              }
            />
            <Route
              path="/guardian-dashboard"
              element={
                <RequireAuth>
                  <GuardianDashboard />
                </RequireAuth>
              }
            />

            <Route
              path="/live-status"
              element={
                <RequireAuth>
                  <LiveStatus />
                </RequireAuth>
              }
            />
            <Route
              path="/dashboard"
              element={<Navigate to="/live-status" replace />}
            />
            <Route
              path="/history"
              element={
                <RequireAuth>
                  <History />
                </RequireAuth>
              }
            />
            <Route
              path="/alerts"
              element={
                <RequireAuth>
                  <Alerts />
                </RequireAuth>
              }
            />
            <Route
              path="/trend"
              element={
                <RequireAuth>
                  <Trend />
                </RequireAuth>
              }
            />
            <Route
              path="/reports"
              element={
                <RequireAuth>
                  <Reports />
                </RequireAuth>
              }
            />

            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
        </BrowserRouter>
      </WebSocketProvider>
    </PatientProvider>
  );
}
