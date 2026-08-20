import { usePatient } from '../contexts/PatientContext';

export default function PatientSelector() {
  const { currentUser, patients, selectedPatientId, setSelectedPatientId } = usePatient();

  // Nothing to pick between: either not a guardian, or no linked patients yet.
  if (!patients || patients.length === 0) return null;

  return (
    <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 10 }}>
      <label htmlFor="patient-select" className="stat-label" style={{ margin: 0 }}>
        Viewing
      </label>
      <select
        id="patient-select"
        value={String(selectedPatientId ?? currentUser?.id ?? '')}
        onChange={(e) => setSelectedPatientId(e.target.value)}
        style={{
          padding: '6px 10px',
          borderRadius: 8,
          border: '1px solid #D8DEDF',
          background: '#fff',
          fontSize: 14,
        }}
      >
        {currentUser && (
          <option value={String(currentUser.id)}>
            {currentUser.full_name || currentUser.username} (me)
          </option>
        )}
        {patients.map((p) => (
          <option key={p.id} value={String(p.id)}>
            {p.full_name || p.username}
          </option>
        ))}
      </select>
    </div>
  );
}
