import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ZAxis,
} from 'recharts'

const COURSE_COLORS = [
  'var(--color-primary)',
  'var(--color-teal)',
  'var(--color-purple)',
  'var(--color-yellow)',
  'var(--color-red)',
  'var(--color-green)',
]

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  if (!d) return null
  return (
    <div style={{ background: '#1A2233', border: 'none', fontSize: 12, color: '#fff', borderRadius: 8, padding: '8px 12px' }}>
      <p style={{ color: '#8E97A8', marginBottom: 4, fontSize: 11 }}>{d.course_code} · {d.date}</p>
      <p>Temp: <strong>{d.avg_temp}°C</strong></p>
      <p>Attendance: <strong>{Math.round(d.attendance_rate * 100)}%</strong></p>
    </div>
  )
}

export default function CorrelationScatter({ data = [] }) {
  // Group by course_code for distinct colours
  const courses = [...new Set(data.map(d => d.course_code))]
  const byCode = {}
  courses.forEach(c => { byCode[c] = data.filter(d => d.course_code === c) })

  return (
    <div style={{
      background: 'var(--color-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 12,
      padding: '20px 24px',
      boxShadow: 'var(--shadow-card)',
    }}>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontWeight: 600, fontSize: 'var(--text-base)', color: 'var(--color-text-primary)', marginBottom: 4 }}>
        Temperature vs. Attendance
      </p>
      <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>Each dot is one session.</p>

      {data.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--color-text-muted)', fontSize: 13 }}>
          Not enough session data for correlation analysis.
        </div>
      ) : (
        <>
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 4, right: 8, bottom: 0, left: -8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis
                  dataKey="avg_temp"
                  name="Temperature"
                  type="number"
                  domain={['auto', 'auto']}
                  label={{ value: 'Avg Temp (°C)', position: 'insideBottom', offset: -2, fontSize: 11, fill: 'var(--color-text-muted)' }}
                  tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  dataKey="attendance_rate"
                  name="Attendance"
                  type="number"
                  domain={[0, 1]}
                  tickFormatter={v => `${Math.round(v * 100)}%`}
                  tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
                  axisLine={false}
                  tickLine={false}
                  width={38}
                />
                <ZAxis range={[40, 40]} />
                <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />
                {courses.map((code, i) => (
                  <Scatter
                    key={code}
                    name={code}
                    data={byCode[code]}
                    fill={COURSE_COLORS[i % COURSE_COLORS.length]}
                    opacity={0.75}
                  />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          {/* Legend */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 10 }}>
            {courses.map((code, i) => (
              <div key={code} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: COURSE_COLORS[i % COURSE_COLORS.length], flexShrink: 0 }} />
                <span style={{ fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>{code}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
