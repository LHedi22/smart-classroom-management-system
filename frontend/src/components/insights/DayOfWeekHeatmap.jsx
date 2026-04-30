const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const SLOTS = ['Morning', 'Afternoon', 'Evening']

function rateToColor(rate) {
  if (rate == null) return 'var(--color-bg)'
  const intensity = Math.round(rate * 10) / 10
  if (intensity >= 0.85) return 'rgba(0,117,201,0.85)'
  if (intensity >= 0.70) return 'rgba(0,117,201,0.60)'
  if (intensity >= 0.55) return 'rgba(0,117,201,0.38)'
  if (intensity >= 0.40) return 'rgba(0,117,201,0.20)'
  return 'rgba(0,117,201,0.08)'
}

function rateToTextColor(rate) {
  if (rate == null) return 'var(--color-text-muted)'
  return rate >= 0.70 ? '#fff' : 'var(--color-text-secondary)'
}

export default function DayOfWeekHeatmap({ data = [] }) {
  // Convert flat array to lookup: grid[day][slot] = avg_rate
  const grid = {}
  data.forEach(({ day_of_week, hour_slot, avg_rate }) => {
    if (!grid[day_of_week]) grid[day_of_week] = {}
    grid[day_of_week][hour_slot] = avg_rate
  })

  return (
    <div style={{
      background: 'var(--color-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 12,
      padding: '20px 24px',
      boxShadow: 'var(--shadow-card)',
    }}>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontWeight: 600, fontSize: 'var(--text-base)', color: 'var(--color-text-primary)', marginBottom: 16 }}>
        Attendance by Day &amp; Time
      </p>

      {data.length === 0 ? (
        <p style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: '24px 0', fontSize: 13 }}>No data yet</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '72px repeat(7, 1fr)', gap: 4, minWidth: 500 }}>
            {/* Header row */}
            <div />
            {DAYS.map(d => (
              <div key={d} style={{ textAlign: 'center', fontSize: 11, fontWeight: 700, color: 'var(--color-text-muted)', paddingBottom: 4 }}>{d}</div>
            ))}

            {/* Data rows */}
            {SLOTS.map((slot, slotIdx) => (
              <>
                <div key={`label-${slotIdx}`} style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', paddingRight: 8 }}>
                  {slot}
                </div>
                {DAYS.map((_, dayIdx) => {
                  const rate = grid[dayIdx]?.[slotIdx] ?? null
                  return (
                    <div
                      key={`${dayIdx}-${slotIdx}`}
                      title={rate != null ? `${Math.round(rate * 100)}%` : 'No data'}
                      style={{
                        height: 44,
                        borderRadius: 6,
                        background: rateToColor(rate),
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 11,
                        fontWeight: 600,
                        color: rateToTextColor(rate),
                        transition: 'transform 0.1s',
                        cursor: rate != null ? 'default' : 'default',
                        border: '1px solid var(--color-border)',
                      }}
                    >
                      {rate != null ? `${Math.round(rate * 100)}%` : '—'}
                    </div>
                  )
                })}
              </>
            ))}
          </div>
        </div>
      )}

      {/* Legend */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 14, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, color: 'var(--color-text-muted)', marginRight: 4 }}>Rate:</span>
        {[['Low', 'rgba(0,117,201,0.08)'], ['Mid', 'rgba(0,117,201,0.38)'], ['High', 'rgba(0,117,201,0.85)']].map(([label, bg]) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 14, height: 14, borderRadius: 3, background: bg, border: '1px solid var(--color-border)' }} />
            <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
