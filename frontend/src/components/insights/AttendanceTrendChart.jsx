import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, defs, linearGradient,
} from 'recharts'

function EmptyState() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--color-text-muted)', gap: 8 }}>
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
      <p style={{ fontSize: 13 }}>No trend data yet</p>
    </div>
  )
}

export default function AttendanceTrendChart({ data = [], height = 220, title = 'Attendance Trend' }) {
  return (
    <div style={{
      background: 'var(--color-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 12,
      padding: '20px 24px',
      boxShadow: 'var(--shadow-card)',
    }}>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontWeight: 600, fontSize: 'var(--text-base)', color: 'var(--color-text-primary)', marginBottom: 16 }}>
        {title}
      </p>
      <div style={{ height }}>
        {data.length === 0 ? <EmptyState /> : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
              <defs>
                <linearGradient id="at-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="var(--color-primary)" stopOpacity={0.18} />
                  <stop offset="95%" stopColor="var(--color-primary)" stopOpacity={0.01} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis
                dataKey="week_label"
                tick={{ fontSize: 11, fill: 'var(--color-text-muted)', fontFamily: 'Inter, sans-serif' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[0, 1]}
                tickFormatter={v => `${Math.round(v * 100)}%`}
                tick={{ fontSize: 11, fill: 'var(--color-text-muted)', fontFamily: 'Inter, sans-serif' }}
                axisLine={false}
                tickLine={false}
                width={40}
              />
              <Tooltip
                contentStyle={{ background: '#1A2233', border: 'none', fontSize: 12, color: '#fff', borderRadius: 8, padding: '8px 12px' }}
                formatter={v => [`${Math.round(v * 100)}%`, 'Attendance Rate']}
                labelStyle={{ color: '#8E97A8', marginBottom: 4 }}
              />
              <Area
                type="monotone"
                dataKey="attendance_rate"
                stroke="var(--color-primary)"
                strokeWidth={2}
                fill="url(#at-grad)"
                dot={{ r: 3, fill: 'var(--color-primary)', strokeWidth: 0 }}
                activeDot={{ r: 5, fill: 'var(--color-primary)' }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
