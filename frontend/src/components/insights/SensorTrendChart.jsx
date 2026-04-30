import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'

const LINES = [
  { key: 'temp_avg',         label: 'Temperature (°C)', color: 'var(--color-red)',      yAxisId: 'temp' },
  { key: 'humidity_avg',     label: 'Humidity (%)',     color: 'var(--color-primary)',  yAxisId: 'pct' },
  { key: 'air_quality_avg',  label: 'Air Quality (ppm)', color: 'var(--color-yellow)', yAxisId: 'aq' },
]

export default function SensorTrendChart({ data = [], height = 240 }) {
  return (
    <div style={{
      background: 'var(--color-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 12,
      padding: '20px 24px',
      boxShadow: 'var(--shadow-card)',
    }}>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontWeight: 600, fontSize: 'var(--text-base)', color: 'var(--color-text-primary)', marginBottom: 16 }}>
        Environmental Trends
      </p>
      <div style={{ height }}>
        {data.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--color-text-muted)', fontSize: 13 }}>
            No sensor data yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: 'var(--color-text-muted)', fontFamily: 'Inter, sans-serif' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={d => {
                  const parts = d.split('-')
                  return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : d
                }}
              />
              {/* Single Y-axis; each line has its own domain so values overlap visually */}
              <YAxis
                yAxisId="temp"
                domain={[15, 40]}
                tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                axisLine={false}
                tickLine={false}
                width={28}
                hide
              />
              <YAxis yAxisId="pct"    hide domain={[0, 100]} />
              <YAxis yAxisId="aq"     hide domain={[0, 600]} />
              <Tooltip
                contentStyle={{ background: '#1A2233', border: 'none', fontSize: 12, color: '#fff', borderRadius: 8, padding: '8px 12px' }}
                labelStyle={{ color: '#8E97A8', marginBottom: 4 }}
                formatter={(v, name) => [typeof v === 'number' ? v.toFixed(1) : v, name]}
              />
              <Legend
                iconType="circle"
                iconSize={8}
                wrapperStyle={{ fontSize: 11, fontFamily: 'Inter, sans-serif', paddingTop: 8 }}
              />
              {LINES.map(({ key, label, color, yAxisId }) => (
                <Line
                  key={key}
                  yAxisId={yAxisId}
                  type="monotone"
                  dataKey={key}
                  name={label}
                  stroke={color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
