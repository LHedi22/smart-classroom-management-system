import { useState, useEffect, useRef } from 'react'
import {
  AreaChart, Area, ResponsiveContainer, Tooltip,
} from 'recharts'
import { useSensor } from '../context/SensorContext'
import DemoModeBanner from '../components/DemoModeBanner'
import { getSessions } from '../api/sessions'
import { getSessionSensorsLatest, getSessionSensorsSummary } from '../api/sensors'
import client from '../api/client'

// ── Sensor icon SVGs ──────────────────────────────────────────────────────

const TempIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/>
  </svg>
)
const WindIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/><path d="M9.6 4.6A2 2 0 1 1 11 8H2"/>
    <path d="M12.6 19.4A2 2 0 1 0 14 16H2"/>
  </svg>
)
const DropletIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/>
  </svg>
)
const VolumeIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
    <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
  </svg>
)

// ── Constants ─────────────────────────────────────────────────────────────

const SENSOR_META = {
  temperature: { label: 'Temperature', unit: '°C',   color: '#EC0044', iconBg: 'rgba(236,0,68,0.1)',    Icon: TempIcon },
  humidity:    { label: 'Humidity',    unit: '%',    color: '#0075C9', iconBg: 'rgba(0,117,201,0.1)',   Icon: DropletIcon },
  air_quality: { label: 'CO₂',         unit: ' ppm', color: '#FFB700', iconBg: 'rgba(255,183,0,0.12)',  Icon: WindIcon },
  sound:       { label: 'Sound',       unit: '',     color: '#572F87', iconBg: 'rgba(87,47,135,0.1)',   Icon: VolumeIcon },
}

const STATUS_CHIP = {
  present: 'status-chip-success',
  absent:  'status-chip-danger',
  late:    'status-chip-warning',
  excused: 'status-chip-neutral',
}

const DISPLAY_BADGE = {
  live:     'status-chip-success',
  upcoming: 'status-chip-warning',
  done:     'status-chip-neutral',
}

const SPARK_MAX = 20

// ── Helpers ───────────────────────────────────────────────────────────────

function fmt(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function fmtDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

// ── Sub-components ────────────────────────────────────────────────────────

function StatusBadge({ ds }) {
  const label = ds === 'live' ? '● Live' : ds === 'upcoming' ? 'Upcoming' : 'Done'
  return <span className={DISPLAY_BADGE[ds] ?? DISPLAY_BADGE.done}>{label}</span>
}

function SessionCard({ session, selected, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%',
        textAlign: 'left',
        padding: '12px 14px',
        borderRadius: 10,
        border: selected
          ? '1.5px solid rgba(0,117,201,0.6)'
          : '1px solid var(--color-border)',
        background: selected
          ? 'rgba(0,117,201,0.07)'
          : 'var(--color-surface)',
        cursor: 'pointer',
        transition: 'all 0.15s ease',
        outline: 'none',
        boxShadow: selected ? '0 1px 4px rgba(0,117,201,0.12)' : 'none',
        display: 'flex',
        flexDirection: 'column',
        gap: 3,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 2 }}>
        <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)', lineHeight: 1.35, flex: 1 }}>
          {session.course_name || session.course?.name || '—'}
        </p>
        <StatusBadge ds={session.display_status} />
      </div>
      <p style={{ fontSize: 12, color: 'var(--color-text-muted)', fontWeight: 500 }}>
        {session.course_code || session.course?.code}
      </p>
      <p style={{ fontSize: 11.5, color: 'var(--color-text-muted)' }}>
        {fmtDate(session.started_at)} · {fmt(session.started_at)}
        {session.ended_at ? ` – ${fmt(session.ended_at)}` : ''}
      </p>
      {(session.present_count > 0 || session.total_students > 0) && (
        <p style={{ fontSize: 11.5, color: 'var(--color-text-secondary)', marginTop: 1 }}>
          <span style={{ color: 'var(--color-forest)', fontWeight: 700 }}>{session.present_count}</span>
          <span style={{ color: 'var(--color-text-muted)' }}>/{session.total_students} present</span>
        </p>
      )}
    </button>
  )
}

function SessionGroup({ title, sessions, selectedId, onSelect }) {
  if (!sessions.length) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '0 2px' }}>
        <p style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--color-text-muted)' }}>
          {title}
        </p>
        <span className="status-chip-neutral" style={{ fontSize: 10, padding: '1px 6px' }}>
          {sessions.length}
        </span>
      </div>
      {sessions.map(s => (
        <SessionCard
          key={s.id}
          session={s}
          selected={s.id === selectedId}
          onClick={() => onSelect(s.id)}
        />
      ))}
    </div>
  )
}

// ── Attendance tab ────────────────────────────────────────────────────────

function AttendanceTab({ sessionId, isLive }) {
  const { attendance: wsAttendance } = useSensor()
  const [records,    setRecords]    = useState([])
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState(null)
  const [recogRunning, setRecogRunning] = useState(false)
  const [recogBusy,    setRecogBusy]   = useState(false)

  // Always-current ref so the async init can read the latest WS events at resolve time
  const wsAttendanceRef = useRef([])
  useEffect(() => { wsAttendanceRef.current = wsAttendance }, [wsAttendance])

  useEffect(() => {
    if (!sessionId) return
    setLoading(true)
    setError(null)
    setRecords([])
    const init = async () => {
      try {
        await client.post(`/sessions/${sessionId}/mark-absent`)
      } catch {}
      try {
        const r = await client.get(`/sessions/${sessionId}/attendance`)
        // Apply any WS events that arrived during loading — avoids the race condition
        // where events fire before records are set and the WS effect has nothing to patch
        const pending = wsAttendanceRef.current
        const roster = pending.length
          ? r.data.map(rec => {
              const ev = pending.find(e => e.student_id === rec.student_id)
              return ev && rec.status !== 'present'
                ? { ...rec, status: ev.status ?? 'present', detected_at: ev.detected_at }
                : rec
            })
          : r.data
        setRecords(roster)
      } catch {
        setError('Failed to load attendance')
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [sessionId])

  // Polling fallback for live sessions — patches only changed rows, no flicker
  useEffect(() => {
    if (!isLive || !sessionId) return
    const id = setInterval(async () => {
      try {
        const r = await client.get(`/sessions/${sessionId}/attendance`)
        setRecords(prev => {
          const byStudent = Object.fromEntries(r.data.map(s => [s.student_id, s]))
          let changed = false
          const next = prev.map(rec => {
            const fresh = byStudent[rec.student_id]
            if (!fresh || fresh.status === rec.status) return rec
            changed = true
            return fresh
          })
          return changed ? next : prev
        })
      } catch {}
    }, 3000)
    return () => clearInterval(id)
  }, [sessionId, isLive])

  const LAUNCHER = 'http://localhost:8001'

  useEffect(() => {
    if (!isLive) return
    fetch(`${LAUNCHER}/status`)
      .then(r => r.json())
      .then(d => setRecogRunning(d.running))
      .catch(() => {})
  }, [isLive, sessionId])

  async function toggleRecognition() {
    setRecogBusy(true)
    try {
      const path = recogRunning ? '/stop' : '/start'
      const r = await fetch(`${LAUNCHER}${path}`, { method: 'POST' })
      const d = await r.json()
      if (d.error) throw new Error(d.error)
      setRecogRunning(d.running)

      if (d.running) {
        // Ensure all enrolled students have an absent record, then refresh the
        // full roster so every student is visible before recognition flips them.
        try { await client.post(`/sessions/${sessionId}/mark-absent`) } catch {}
        try {
          const roster = await client.get(`/sessions/${sessionId}/attendance`)
          setRecords(roster.data)
        } catch {}
      }
    } catch (e) {
      alert(e.message ?? 'Could not reach demo launcher. Run: python demo_launcher.py')
    } finally {
      setRecogBusy(false)
    }
  }

  // WS live updates: flip the matching virtual absent entry → present in-place
  useEffect(() => {
    if (!isLive || !wsAttendance.length) return
    setRecords(prev => {
      let changed = false
      const next = prev.map(r => {
        const ev = wsAttendance.find(e => e.student_id === r.student_id)
        if (!ev || r.status === 'present') return r
        changed = true
        return { ...r, status: ev.status ?? 'present', detected_at: ev.detected_at }
      })
      return changed ? next : prev
    })
  }, [wsAttendance, sessionId, isLive])

  if (loading) return (
    <div className="empty-state">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%' }}>
        {[1,2,3].map(i => (
          <div key={i} className="skeleton" style={{ height: 40, borderRadius: 8, opacity: 0.7 - i * 0.1 }} />
        ))}
      </div>
    </div>
  )

  if (error) return (
    <div className="empty-state">
      <div className="empty-state-icon" style={{ background: 'rgba(236,0,68,0.06)', borderColor: 'rgba(236,0,68,0.18)' }}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--color-red)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
      </div>
      <p className="empty-state-title" style={{ color: 'var(--color-red)' }}>{error}</p>
    </div>
  )

  const present = records.filter(r => r.status === 'present').length

  if (records.length === 0) return (
    <div className="empty-state">
      <div className="empty-state-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
      </div>
      <p className="empty-state-title">No students enrolled</p>
      <p className="empty-state-desc">Enroll students in this course to see their attendance here.</p>
    </div>
  )

  return (
    <div>
      {/* Demo: auto attendance button — live sessions only */}
      {isLive && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: 12, marginBottom: 12,
          padding: '8px 12px', borderRadius: 8,
          border: `1px dashed ${recogRunning ? 'rgba(0,122,119,0.45)' : 'rgba(255,183,0,0.45)'}`,
          background: recogRunning ? 'rgba(0,122,119,0.06)' : 'rgba(255,183,0,0.05)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            {recogRunning && (
              <span style={{
                width: 7, height: 7, borderRadius: '50%',
                background: 'var(--color-teal)', display: 'inline-block',
                animation: 'pulse-dot 2.2s ease-in-out infinite',
              }} />
            )}
            <span style={{ fontSize: 11, fontWeight: 600, color: recogRunning ? '#007A77' : '#7A5B00' }}>
              {recogRunning ? 'Face recognition running…' : 'Live Demo — Automated Attendance'}
            </span>
          </div>
          <button
            onClick={toggleRecognition}
            disabled={recogBusy}
            style={{
              fontSize: 11, fontWeight: 700, padding: '4px 12px', borderRadius: 6,
              border: 'none', cursor: recogBusy ? 'not-allowed' : 'pointer',
              background: recogRunning ? 'var(--color-red)' : 'var(--color-teal)',
              color: '#fff', opacity: recogBusy ? 0.6 : 1, transition: 'opacity 0.15s',
            }}
          >
            {recogBusy ? '…' : recogRunning ? 'Stop' : 'Start Recognition'}
          </button>
        </div>
      )}

      <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 12 }}>
        <span style={{ color: 'var(--color-forest)', fontWeight: 700 }}>{present}</span>
        {' / '}{records.length} enrolled
      </p>
      <div style={{ overflowY: 'auto', maxHeight: '52vh' }}>
        <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
          <thead style={{ position: 'sticky', top: 0 }}>
            <tr className="table-head-row">
              <th style={{ textAlign: 'left', padding: '10px 12px' }}>Student</th>
              <th style={{ textAlign: 'left', padding: '10px 12px' }}>ID</th>
              <th style={{ textAlign: 'left', padding: '10px 12px' }}>Status</th>
              <th style={{ textAlign: 'left', padding: '10px 12px' }}>Time</th>
            </tr>
          </thead>
          <tbody>
            {records.map(r => {
              const isVirtual = !r.id
              return (
                <tr key={r.id ?? `virtual-${r.student_id}`} className="table-row" style={{ opacity: isVirtual ? 0.72 : 1 }}>
                  <td style={{ padding: '11px 12px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                    {r.student_name || r.name}
                  </td>
                  <td style={{ padding: '11px 12px', color: 'var(--color-text-muted)', fontSize: 12, fontFamily: 'monospace' }}>
                    {r.student_number || '—'}
                  </td>
                  <td style={{ padding: '11px 12px' }}>
                    <span className={STATUS_CHIP[r.status] ?? STATUS_CHIP.absent}>{r.status}</span>
                  </td>
                  <td style={{ padding: '11px 12px', color: 'var(--color-text-muted)', fontSize: 12 }}>
                    {isVirtual
                      ? <span style={{ fontStyle: 'italic', fontSize: 11 }}>not detected</span>
                      : fmt(r.detected_at)
                    }
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Sensor cards ──────────────────────────────────────────────────────────

function LiveSensorCard({ type, value, sparkData }) {
  const meta = SENSOR_META[type]
  const displayVal = type === 'sound'
    ? (value != null ? (value > 0 ? 'Active' : 'Quiet') : '—')
    : value != null ? `${Number(value).toFixed(1)}${meta.unit}` : '—'

  return (
    <div style={{
      borderRadius: 12,
      border: '1px solid var(--color-border)',
      background: 'var(--color-surface)',
      padding: '14px 16px',
      boxShadow: 'var(--shadow-card)',
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 36, height: 36, borderRadius: '50%',
          background: meta.iconBg,
          color: meta.color,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          <meta.Icon />
        </div>
        <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          {meta.label}
        </p>
      </div>
      <p style={{
        fontFamily: "'DM Sans', sans-serif",
        fontSize: 26,
        fontWeight: 700,
        color: 'var(--color-text-primary)',
        letterSpacing: '-0.02em',
        lineHeight: 1,
      }}>
        {displayVal}
      </p>
      {sparkData && sparkData.length > 1 && type !== 'sound' && (
        <div style={{ height: 36, marginTop: 2 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sparkData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id={`g-${type}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={meta.color} stopOpacity={0.18} />
                  <stop offset="95%" stopColor={meta.color} stopOpacity={0.01} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="v"
                stroke={meta.color}
                strokeWidth={1.5}
                fill={`url(#g-${type})`}
                dot={false}
                isAnimationActive={false}
              />
              <Tooltip
                contentStyle={{ background: '#1A2233', border: 'none', fontSize: 11, color: '#fff', borderRadius: 6, padding: '4px 10px' }}
                formatter={v => [`${Number(v).toFixed(1)}${meta.unit}`, meta.label]}
                labelFormatter={() => ''}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

function DoneSensorCard({ type, stats }) {
  const meta = SENSOR_META[type]
  if (!stats) return (
    <div style={{
      borderRadius: 12, border: '1px solid var(--color-border)', background: 'var(--color-surface)',
      padding: '14px 16px', boxShadow: 'var(--shadow-card)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'rgba(138,151,168,0.1)', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <meta.Icon />
        </div>
        <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>{meta.label}</p>
      </div>
      <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>No data recorded</p>
    </div>
  )
  const fv = v => type !== 'sound' ? `${Number(v).toFixed(1)}${meta.unit}` : v
  return (
    <div style={{ borderRadius: 12, border: '1px solid var(--color-border)', background: 'var(--color-surface)', padding: '14px 16px', boxShadow: 'var(--shadow-card)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <div style={{ width: 36, height: 36, borderRadius: '50%', background: meta.iconBg, color: meta.color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <meta.Icon />
        </div>
        <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>{meta.label}</p>
      </div>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)', letterSpacing: '-0.02em' }}>{fv(stats.avg)} <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text-muted)', fontFamily: 'Inter, sans-serif' }}>avg</span></p>
      <div style={{ display: 'flex', gap: 16, marginTop: 6 }}>
        <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>↓ {fv(stats.min)}</span>
        <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>↑ {fv(stats.max)}</span>
      </div>
    </div>
  )
}

// ── Sensors tab ───────────────────────────────────────────────────────────

function SensorsTab({ sessionId, displayStatus, sparkData }) {
  const { sensors: wsSensors, isDemoMode } = useSensor()
  const [summary,    setSummary]    = useState(null)
  const [pollLatest, setPollLatest] = useState(null)
  const [loading,    setLoading]    = useState(false)
  const [error,      setError]      = useState(null)
  const pollRef = useRef(null)

  useEffect(() => {
    if (displayStatus !== 'done') return
    setSummary(null)
    setLoading(true)
    setError(null)
    getSessionSensorsSummary(sessionId)
      .then(d => setSummary(d))
      .catch(() => setError('No sensor data available for this session'))
      .finally(() => setLoading(false))
  }, [sessionId, displayStatus])

  useEffect(() => {
    clearInterval(pollRef.current)
    if (displayStatus !== 'live') { setPollLatest(null); return }
    const poll = () => {
      getSessionSensorsLatest(sessionId)
        .then(d => setPollLatest(d.sensors ?? {}))
        .catch(() => {})
    }
    poll()
    pollRef.current = setInterval(poll, 5_000)
    return () => clearInterval(pollRef.current)
  }, [sessionId, displayStatus])

  if (displayStatus === 'upcoming') return (
    <div className="empty-state">
      <div className="empty-state-icon">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </svg>
      </div>
      <p className="empty-state-title">Session not started</p>
      <p className="empty-state-desc">Sensor readings will appear once the session is live.</p>
    </div>
  )

  if (displayStatus === 'done') {
    if (loading) return <div className="empty-state"><div className="skeleton" style={{ width: '100%', height: 120, borderRadius: 12 }} /></div>
    if (error) return (
      <div className="empty-state">
        <p className="empty-state-title" style={{ color: 'var(--color-text-muted)' }}>{error}</p>
      </div>
    )
    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {Object.keys(SENSOR_META).map(type => (
          <DoneSensorCard key={type} type={type} stats={summary?.[type]} />
        ))}
      </div>
    )
  }

  const src = isDemoMode ? pollLatest : wsSensors
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
      {Object.keys(SENSOR_META).map(type => {
        const val = src?.[type]?.value ?? pollLatest?.[type]?.value ?? null
        return (
          <LiveSensorCard
            key={type}
            type={type}
            value={val}
            sparkData={sparkData[type] ?? []}
          />
        )
      })}
    </div>
  )
}

// ── Detail panel ──────────────────────────────────────────────────────────

function DetailPanel({ session, sparkData }) {
  const [tab, setTab] = useState('attendance')
  useEffect(() => setTab('attendance'), [session?.id])

  if (!session) return (
    <div className="empty-state" style={{ height: '100%' }}>
      <div className="empty-state-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
          <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
        </svg>
      </div>
      <p className="empty-state-title">Select a session</p>
      <p className="empty-state-desc">Choose a session from the left panel to view attendance records and sensor data.</p>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Session header */}
      <div className="panel-header" style={{ flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 3 }}>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 15, fontWeight: 700, color: 'var(--color-text-primary)' }}>
            {session.course_name || session.course?.name}
          </p>
          <StatusBadge ds={session.display_status} />
        </div>
        <p style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
          {session.course_code || session.course?.code} · Room {session.room_id} ·{' '}
          {fmtDate(session.started_at)} {fmt(session.started_at)}
          {session.ended_at ? ` – ${fmt(session.ended_at)}` : ''}
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)', flexShrink: 0 }}>
        {['attendance', 'sensors'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={tab === t ? 'tab-btn-active' : 'tab-btn-inactive'}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
        {tab === 'attendance'
          ? <AttendanceTab key={session.id} sessionId={session.id} isLive={session.display_status === 'live'} />
          : <SensorsTab key={session.id} sessionId={session.id} displayStatus={session.display_status} sparkData={sparkData} />
        }
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

function comfortColor(score) {
  if (score >= 70) return 'var(--color-forest)'
  if (score >= 40) return '#7A5B00'
  return 'var(--color-red)'
}

export default function Dashboard() {
  const { sensors: wsSensors, isDemoMode, isConnected } = useSensor()

  const [sessions,    setSessions]    = useState([])
  const [selectedId,  setSelectedId]  = useState(null)
  const [loadingSess, setLoadingSess] = useState(true)
  const [sessError,   setSessError]   = useState(null)
  const [overview,    setOverview]    = useState(null)

  const sparkRef    = useRef({ temperature: [], humidity: [], air_quality: [], sound: [] })
  const [sparkData, setSparkData]   = useState(sparkRef.current)
  const lastPushedRef = useRef({})

  useEffect(() => {
    client.get('/insights/overview').then(r => setOverview(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    setLoadingSess(true)
    getSessions()
      .then(data => {
        setSessions(data)
        const live     = data.find(s => s.display_status === 'live')
        const upcoming = data.find(s => s.display_status === 'upcoming')
        const pick     = live ?? upcoming ?? null
        if (pick) setSelectedId(pick.id)
      })
      .catch(() => setSessError('Could not load sessions'))
      .finally(() => setLoadingSess(false))
  }, [])

  useEffect(() => {
    const selected = sessions.find(s => s.id === selectedId)
    if (!selected || selected.display_status !== 'live') return
    let changed = false
    const next = { ...sparkRef.current }
    Object.entries(wsSensors).forEach(([type, data]) => {
      if (data?.value != null && data.value !== lastPushedRef.current[type]) {
        lastPushedRef.current[type] = data.value
        next[type] = [...(next[type] ?? []), { v: data.value }].slice(-SPARK_MAX)
        changed = true
      }
    })
    if (changed) {
      sparkRef.current = next
      setSparkData({ ...next })
    }
  }, [wsSensors, selectedId, sessions])

  const selectedSession = sessions.find(s => s.id === selectedId) ?? null
  const live     = sessions.filter(s => s.display_status === 'live')
  const upcoming = sessions.filter(s => s.display_status === 'upcoming')
  const done     = sessions.filter(s => s.display_status === 'done')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 12 }}>
    {/* Insights mini-strip */}
    {overview && (
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        {/* Comfort score pill */}
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 10, padding: '7px 14px', boxShadow: 'var(--shadow-card)', fontSize: 12,
        }}>
          <span style={{ color: 'var(--color-text-muted)', fontWeight: 600 }}>Comfort</span>
          <span style={{ fontFamily: "'DM Sans', sans-serif", fontWeight: 700, fontSize: 16, color: comfortColor(overview.comfort_score ?? 0) }}>
            {overview.comfort_score ?? '—'}
          </span>
          <span style={{ color: 'var(--color-text-muted)' }}>/100</span>
        </div>

        {/* At-risk warning */}
        {(overview.at_risk_count ?? 0) > 0 && (
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            background: 'rgba(236,0,68,0.06)', border: '1px solid rgba(236,0,68,0.20)',
            borderRadius: 10, padding: '7px 14px', fontSize: 12, color: 'var(--color-red)', fontWeight: 500,
          }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            <span><strong>{overview.at_risk_count}</strong> students at risk across your courses.</span>
            <a href="/insights" style={{ color: 'var(--color-red)', fontWeight: 700, textDecoration: 'underline' }}>View in Insights →</a>
          </div>
        )}
      </div>
    )}
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'minmax(0, 320px) 1fr',
      flex: 1,
      gap: 16,
      minHeight: 0,
    }}>
      {/* ── Session list ───────────────────────────────────────────── */}
      <aside style={{
        borderRadius: 12,
        border: '1px solid var(--color-border)',
        background: 'var(--color-surface)',
        boxShadow: 'var(--shadow-card)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        minHeight: 0,
      }}>
        <div className="panel-header" style={{ flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <h1 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 15, fontWeight: 700, color: 'var(--color-text-primary)' }}>
              Sessions
            </h1>
            {sessions.length > 0 && (
              <span className="status-chip-neutral" style={{ fontSize: 10, padding: '2px 7px' }}>
                {sessions.length} total
              </span>
            )}
          </div>
          <p style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
            {isConnected
              ? <><span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--color-teal)', display: 'inline-block', animation: 'pulse-dot 2.2s ease-in-out infinite' }} /><span style={{ color: '#007A77' }}>Connected</span></>
              : <><span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--color-text-muted)', display: 'inline-block' }} /><span style={{ color: 'var(--color-text-muted)' }}>Offline</span></>
            }
          </p>
        </div>

        <DemoModeBanner isDemoMode={isDemoMode} />

        <div style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {loadingSess ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 8 }}>
              {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height: 72, borderRadius: 10 }} />)}
            </div>
          ) : sessError ? (
            <p style={{ fontSize: 13, color: 'var(--color-red)', textAlign: 'center', paddingTop: 24 }}>{sessError}</p>
          ) : sessions.length === 0 ? (
            <div className="empty-state">
              <p className="empty-state-title">No sessions yet</p>
              <p className="empty-state-desc">Sessions appear here once they are created.</p>
            </div>
          ) : (
            <>
              <SessionGroup title="Live now"  sessions={live}     selectedId={selectedId} onSelect={setSelectedId} />
              <SessionGroup title="Upcoming"  sessions={upcoming} selectedId={selectedId} onSelect={setSelectedId} />
              <SessionGroup title="Past"      sessions={done}     selectedId={selectedId} onSelect={setSelectedId} />
            </>
          )}
        </div>
      </aside>

      {/* ── Detail panel ───────────────────────────────────────────── */}
      <section style={{
        borderRadius: 12,
        border: '1px solid var(--color-border)',
        background: 'var(--color-surface)',
        boxShadow: 'var(--shadow-card)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
      }}>
        <DetailPanel session={selectedSession} sparkData={sparkData} />
      </section>
    </div>
    </div>
  )
}
