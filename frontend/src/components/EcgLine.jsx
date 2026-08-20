export default function EcgLine({ color = '#2FA8A0' }) {
  return (
    <svg viewBox="0 0 300 40" className="ecg-line" preserveAspectRatio="none">
      <polyline
        points="0,20 40,20 55,20 65,5 75,35 85,20 100,20 140,20 155,20 165,5 175,35 185,20 220,20 260,20 275,5 285,35 295,20 300,20"
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
