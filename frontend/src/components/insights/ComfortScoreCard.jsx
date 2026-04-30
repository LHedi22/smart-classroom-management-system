const R = 46
const C = 2 * Math.PI * R
const ARC = C * 0.75
const GAP = C * 0.25

function arcColor(score) {
  if (score >= 70) return 'var(--color-forest)'
  if (score >= 40) return 'var(--color-yellow)'
  return 'var(--color-red)'
}

function worstPenalty(breakdown) {
  if (!breakdown) return null
  const { temp_penalty = 0, humidity_penalty = 0, aq_penalty = 0 } = breakdown
  if (temp_penalty >= humidity_penalty && temp_penalty >= aq_penalty && temp_penalty > 0)
    return 'Temperature is above comfort range'
  if (humidity_penalty >= aq_penalty && humidity_penalty > 0)
    return 'Humidity is above comfort range'
  if (aq_penalty > 0)
    return 'Air quality needs attention'
  return null
}

export default function ComfortScoreCard({ score = 0, breakdown = null, compact = false }) {
  const filled  = (score / 100) * ARC
  const offset  = ARC - filled
  const color   = arcColor(score)
  const penalty = worstPenalty(breakdown)

  if (compact) {
    return (
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 8,
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 10, padding: '8px 14px', boxShadow: 'var(--shadow-card)',
      }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Comfort</span>
        <span style={{ fontFamily: "'DM Sans', sans-serif", fontWeight: 700, fontSize: 18, color, letterSpacing: '-0.02em' }}>{score}</span>
        <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>/100</span>
      </div>
    )
  }

  return (
    <div style={{
      background: 'var(--color-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 12,
      padding: '24px',
      boxShadow: 'var(--shadow-card)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 12,
    }}>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontWeight: 600, fontSize: 'var(--text-base)', color: 'var(--color-text-primary)', alignSelf: 'flex-start', marginBottom: 4 }}>
        Comfort Score
      </p>

      <svg viewBox="0 0 120 120" width="160" height="160">
        {/* Track arc */}
        <circle
          cx="60" cy="60" r={R}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth="10"
          strokeDasharray={`${ARC} ${GAP}`}
          strokeDashoffset={0}
          strokeLinecap="round"
          transform="rotate(135 60 60)"
        />
        {/* Filled arc */}
        <circle
          cx="60" cy="60" r={R}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={`${ARC} ${GAP}`}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(135 60 60)"
          style={{ transition: 'stroke-dashoffset 0.5s ease, stroke 0.3s ease' }}
        />
        {/* Score label */}
        <text
          x="60" y="55"
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="28"
          fontWeight="700"
          fontFamily="'DM Sans', sans-serif"
          fill={color}
        >
          {score}
        </text>
        <text
          x="60" y="74"
          textAnchor="middle"
          fontSize="11"
          fontFamily="Inter, sans-serif"
          fill="var(--color-text-muted)"
        >
          / 100
        </text>
      </svg>

      {penalty ? (
        <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', textAlign: 'center', maxWidth: 200 }}>
          {penalty}
        </p>
      ) : (
        <p style={{ fontSize: 12, color: 'var(--color-forest)', fontWeight: 600 }}>
          Conditions are comfortable
        </p>
      )}
    </div>
  )
}
