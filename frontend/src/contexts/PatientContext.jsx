import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import api from '../api';

const PatientContext = createContext(null);

function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null');
  } catch {
    return null;
  }
}

export function PatientProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(getStoredUser());
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientIdState] = useState(
    localStorage.getItem('selected_patient_id') || null,
  );

  const setSelectedPatientId = useCallback((id) => {
    setSelectedPatientIdState(id);
    if (id) {
      localStorage.setItem('selected_patient_id', id);
    } else {
      localStorage.removeItem('selected_patient_id');
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    api.get('/auth/profile/').then((res) => {
      setCurrentUser(res.data);
      localStorage.setItem('user', JSON.stringify(res.data));
    }).catch(() => {});

    api.get('/auth/my-patients/').then((res) => {
      const list = res.data?.patients ?? res.data ?? [];
      setPatients(Array.isArray(list) ? list : []);
    }).catch(() => {
      setPatients([]);
    });
  }, []);

  // The id to actually query with: whoever is selected, or the logged-in
  // user themselves if nothing is selected / they aren't a guardian.
  const viewingPatientId = selectedPatientId || currentUser?.id || null;
  const isViewingSelf = !selectedPatientId || String(selectedPatientId) === String(currentUser?.id);

  // Query-param helper: only attach patient_id when viewing someone else,
  // so a patient's own dashboard calls stay exactly as before.
  const patientQueryParam = isViewingSelf ? {} : { patient_id: viewingPatientId };

  return (
    <PatientContext.Provider
      value={{
        currentUser,
        patients,
        selectedPatientId: viewingPatientId,
        isViewingSelf,
        setSelectedPatientId,
        patientQueryParam,
      }}
    >
      {children}
    </PatientContext.Provider>
  );
}

export function usePatient() {
  const ctx = useContext(PatientContext);
  if (!ctx) throw new Error('usePatient must be used within a PatientProvider');
  return ctx;
}
