const SessionsIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
  </svg>
)
const PeopleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </svg>
)
const ThermometerIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/>
  </svg>
)
const AlertIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
    <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
  </svg>
)

function trendArrow(current, previous) {
  if (previous == null || current == null) return { symbol: '→', color: 'var(--color-text-muted)' }
  const diff = current - previous
  if (diff >= 0.05) return { symbol: '↑', color: 'var(--color-forest)' }
  if (diff <= -0.05) return { symbol: '↓', color: 'var(--color-red)' }
  return { symbol: '→', color: 'var(--color-text-muted)' }
}

function comfortColor(score) {
  if (score >= 70) return 'var(--color-forest)'
  if (score >= 40) return '#7A5B00'
  return 'var(--color-red)'
}

function KpiCard({ icon, label, value, sub, iconBg, iconColor }) {
  return (
    <div style={{
      background: 'var(--color-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 12,
      padding: '18px 20px',
      boxShadow: 'var(--shadow-card)',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 36, height: 36, borderRadius: '50%',
          background: iconBg,
          color: iconColor,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          {icon}
        </div>
        <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          {label}
        </p>
      </div>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 28, fontWeight: 700, color: 'var(--color-text-primary)', letterSpacing: '-0.02em', lineHeight: 1 }}>
        {value}
      </p>
      {sub && (
        <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: -4 }}>
          {sub}
        </p>
      )}
    </div>
  )
}

export default function KpiCards({ overview, attendanceTrend }) {
  if (!overview) return null

  const prevRate = attendanceTrend?.length >= 2
    ? attendanceTrend[attendanceTrend.length - 2]?.attendance_rate
    : null
  const currRate = attendanceTrend?.length >= 1
    ? attendanceTrend[attendanceTrend.length - 1]?.attendance_rate
    : overview.avg_attendance_rate
  const { symbol, color: arrowColor } = trendArrow(currRate, prevRate)

  const cScore = overview.comfort_score ?? 0

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
      <KpiCard
        icon={<SessionsIcon />}
        label="Total Sessions"
        value={overview.total_sessions ?? '—'}
        iconBg="rgba(0,117,201,0.1)"
        iconColor="var(--color-primary)"
      />
      <KpiCard
        icon={<PeopleIcon />}
        label="Avg Attendance"
        value={`${Math.round((overview.avg_attendance_rate ?? 0) * 100)}%`}
        sub={<span style={{ color: arrowColor, fontWeight: 700 }}>{symbol} vs last week</span>}
        iconBg="rgba(0,175,170,0.1)"
        iconColor="var(--color-teal)"
      />
      <KpiCard
        icon={<ThermometerIcon />}
        label="Comfort Score"
        value={<span style={{ color: comfortColor(cScore) }}>{cScore}</span>}
        sub="0–100, higher is better"
        iconBg="rgba(134,192,87,0.12)"
        iconColor="var(--color-forest)"
      />
      <KpiCard
        icon={<AlertIcon />}
        label="At-Risk Students"
        value={
          <span style={{ color: (overview.at_risk_count ?? 0) > 0 ? 'var(--color-red)' : 'var(--color-forest)' }}>
            {overview.at_risk_count ?? 0}
          </span>
        }
        sub={(overview.at_risk_count ?? 0) > 0 ? 'Needs attention' : 'All on track'}
        iconBg={(overview.at_risk_count ?? 0) > 0 ? 'rgba(236,0,68,0.08)' : 'rgba(134,192,87,0.1)'}
        iconColor={(overview.at_risk_count ?? 0) > 0 ? 'var(--color-red)' : 'var(--color-forest)'}
      />
    </div>
  )
}
