export default function DemoModeBanner({ isDemoMode }) {
  if (!isDemoMode) return null
  return (
    <div className="demo-banner">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, color: '#A07A00' }}>
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      <span>
        <strong style={{ fontWeight: 700 }}>Demo mode</strong> — no hardware connected. Showing simulated sensor data.
      </span>
    </div>
  )
}
