import { useState, useEffect, useRef } from 'react'
import {
  LineChart, Line, ResponsiveContainer, Tooltip,
} from 'recharts'
import { useSensor } from '../context/SensorContext'
import DemoModeBanner from '../components/DemoModeBanner'
import { getSessions, getSession } from '../api/sessions'
import { getSessionSensorsLatest, getSessionSensorsSummary } from '../api/sensors'

// ── Constants ─────────────────────────────────────────────────────────────

const SENSOR_META = {
  temperature: { label: 'Temperature', unit: '°C',   accent: 'border-red-500',    color: '#f87171' },
  humidity:    { label: 'Humidity',    unit: '%',    accent: 'border-blue-500',   color: '#60a5fa' },
  air_quality: { label: 'CO₂',        unit: ' ppm', accent: 'border-yellow-500', color: '#fbbf24' },
  sound:       { label: 'Sound',      unit: '',     accent: 'border-purple-500', color: '#a78bfa' },
}

const STATUS_CHIP = {
  present: 'bg-green-900/60 text-green-300 border border-green-800',
  absent:  'bg-red-900/60 text-red-300 border border-red-800',
  late:    'bg-yellow-900/60 text-yellow-300 border border-yellow-800',
  excused: 'bg-blue-900/60 text-blue-300 border border-blue-800',
}

const DISPLAY_BADGE = {
  live:     'bg-green-900/60 text-green-300 border border-green-800',
  upcoming: 'bg-blue-900/60 text-blue-300 border border-blue-800',
  done:     'bg-gray-700/60 text-gray-400 border border-gray-700',
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
  return (
    <span className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full ${DISPLAY_BADGE[ds] ?? DISPLAY_BADGE.done}`}>
      {ds === 'live' ? '● Live' : ds === 'upcoming' ? 'Upcoming' : 'Done'}
    </span>
  )
}

function SessionCard({ session, selected, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3 rounded-xl border transition-all ${
        selected
          ? 'bg-indigo-900/40 border-indigo-600'
          : 'bg-gray-800/50 border-gray-700 hover:border-gray-600 hover:bg-gray-800'
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <p className="text-sm font-medium text-white leading-tight line-clamp-2">
          {session.course_name || session.course?.name || '—'}
        </p>
        <StatusBadge ds={session.display_status} />
      </div>
      <p className="text-xs text-gray-400">{session.course_code || session.course?.code}</p>
      <p className="text-xs text-gray-500 mt-1">
        {fmtDate(session.started_at)} {fmt(session.started_at)}
        {session.ended_at ? `–${fmt(session.ended_at)}` : ''}
      </p>
      {(session.present_count > 0 || session.total_students > 0) && (
        <p className="text-xs text-gray-500 mt-0.5">
          <span className="text-green-400">{session.present_count}</span>
          /{session.total_students} present
        </p>
      )}
    </button>
  )
}

function SessionGroup({ title, sessions, selectedId, onSelect }) {
  if (!sessions.length) return null
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 px-1">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-gray-500">{title}</p>
        <span className="text-[10px] bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded-full font-medium">
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

// ── Attendance Tab ────────────────────────────────────────────────────────

function AttendanceTab({ sessionId, isLive }) {
  const { attendance: wsAttendance } = useSensor()
  const [detail,  setDetail]  = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    if (!sessionId) return
    setLoading(true)
    setError(null)
    setDetail(null)
    getSession(sessionId)
      .then(d => setDetail(d))
      .catch(() => setError('Failed to load attendance'))
      .finally(() => setLoading(false))
  }, [sessionId])

  // Merge live WS attendance events for active sessions
  useEffect(() => {
    if (!isLive || !wsAttendance.length || !detail) return
    setDetail(prev => {
      if (!prev) return prev
      const merged = [...prev.attendance]
      wsAttendance.forEach(ev => {
        if (!merged.some(r => r.student_id === ev.student_id)) {
          merged.unshift({
            student_id: ev.student_id,
            name: ev.student_name ?? ev.student_id,
            student_number: '',
            status: ev.status ?? 'present',
            detected_at: ev.detected_at,
          })
        }
      })
      return { ...prev, attendance: merged }
    })
  }, [wsAttendance, sessionId, isLive])

  if (loading) return <div className="flex items-center justify-center h-40 text-gray-500 text-sm">Loading…</div>
  if (error)   return <div className="flex items-center justify-center h-40 text-red-400 text-sm">{error}</div>

  const records = detail?.attendance ?? []
  const present = records.filter(r => r.status === 'present').length

  if (records.length === 0) return (
    <div className="flex flex-col items-center justify-center h-40 gap-2 text-gray-600">
      <p className="text-2xl">📋</p>
      <p className="text-sm">No attendance records yet</p>
      {detail?.total_enrolled > 0 && (
        <p className="text-xs text-gray-500">{detail.total_enrolled} students enrolled in this course</p>
      )}
    </div>
  )

  return (
    <div>
      <p className="text-xs text-gray-400 mb-3">
        <span className="text-green-400 font-semibold">{present}</span> / {records.length} students recorded
        {detail?.total_enrolled > 0 && (
          <span className="text-gray-500"> ({detail.total_enrolled} enrolled)</span>
        )}
      </p>
      <div className="overflow-auto max-h-[52vh]">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-gray-900">
            <tr className="text-xs text-gray-500 border-b border-gray-800">
              <th className="text-left px-3 py-2 font-medium">Student</th>
              <th className="text-left px-3 py-2 font-medium">ID</th>
              <th className="text-left px-3 py-2 font-medium">Status</th>
              <th className="text-left px-3 py-2 font-medium">Time</th>
            </tr>
          </thead>
          <tbody>
            {records.map((r, i) => (
              <tr key={r.student_id + i} className="border-b border-gray-800/40 hover:bg-gray-800/30">
                <td className="px-3 py-2.5 text-white font-medium">{r.name}</td>
                <td className="px-3 py-2.5 text-gray-400 text-xs font-mono">{r.student_number || '—'}</td>
                <td className="px-3 py-2.5">
                  <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${STATUS_CHIP[r.status] ?? STATUS_CHIP.absent}`}>
                    {r.status}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-gray-400 text-xs">{fmt(r.detected_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Sensor metric card with sparkline ────────────────────────────────────

function LiveSensorCard({ type, value, sparkData }) {
  const meta = SENSOR_META[type]
  const displayVal = type === 'sound'
    ? (value != null ? (value > 0 ? 'Active' : 'Quiet') : '—')
    : value != null ? `${Number(value).toFixed(1)}${meta.unit}` : '—'

  return (
    <div className={`bg-gray-800/60 rounded-xl p-4 border-l-4 ${meta.accent}`}>
      <p className="text-[10px] uppercase tracking-widest text-gray-400 mb-1">{meta.label}</p>
      <p className="text-2xl font-bold text-white mb-2">{displayVal}</p>
      {sparkData && sparkData.length > 1 && type !== 'sound' && (
        <div className="h-10">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={sparkData}>
              <Line
                type="monotone"
                dataKey="v"
                stroke={meta.color}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
              <Tooltip
                contentStyle={{ background: '#1f2937', border: 'none', fontSize: 11 }}
                formatter={v => [`${Number(v).toFixed(1)}${meta.unit}`, meta.label]}
                labelFormatter={() => ''}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

function DoneSensorCard({ type, stats }) {
  const meta = SENSOR_META[type]
  if (!stats) return (
    <div className="bg-gray-800/60 rounded-xl p-4 border-l-4 border-gray-700">
      <p className="text-[10px] uppercase tracking-widest text-gray-400 mb-1">{meta.label}</p>
      <p className="text-gray-600 text-sm">No data</p>
    </div>
  )
  const fv = v => type !== 'sound' ? `${Number(v).toFixed(1)}${meta.unit}` : v
  return (
    <div className={`bg-gray-800/60 rounded-xl p-4 border-l-4 ${meta.accent}`}>
      <p className="text-[10px] uppercase tracking-widest text-gray-400 mb-1">{meta.label}</p>
      <p className="text-xl font-bold text-white">{fv(stats.avg)} avg</p>
      <div className="flex gap-4 mt-1.5 text-xs text-gray-400">
        <span>↓ {fv(stats.min)}</span>
        <span>↑ {fv(stats.max)}</span>
      </div>
    </div>
  )
}

// ── Sensors Tab ───────────────────────────────────────────────────────────

function SensorsTab({ sessionId, displayStatus, sparkData }) {
  const { sensors: wsSensors, isDemoMode } = useSensor()
  const [summary,    setSummary]    = useState(null)
  const [pollLatest, setPollLatest] = useState(null)
  const [loading,    setLoading]    = useState(false)
  const [error,      setError]      = useState(null)
  const pollRef = useRef(null)

  // Done session: fetch summary once; reset state on session change
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

  // Live session: poll latest every 5s as WS fallback; reset on session change
  useEffect(() => {
    clearInterval(pollRef.current)
    if (displayStatus !== 'live') {
      setPollLatest(null)
      return
    }
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
    <div className="flex flex-col items-center justify-center h-48 gap-2">
      <p className="text-3xl">📅</p>
      <p className="text-gray-400 text-sm text-center">
        Sensor data will appear once the session starts.
      </p>
    </div>
  )

  if (displayStatus === 'done') {
    if (loading) return <div className="flex items-center justify-center h-40 text-gray-500 text-sm">Loading…</div>
    if (error)   return (
      <div className="flex flex-col items-center justify-center h-40 gap-2">
        <p className="text-gray-500 text-sm">{error}</p>
      </div>
    )
    return (
      <div className="grid grid-cols-2 gap-3">
        {Object.keys(SENSOR_META).map(type => (
          <DoneSensorCard key={type} type={type} stats={summary?.[type]} />
        ))}
      </div>
    )
  }

  // Live: prefer WS data; fall back to polled DB values
  const src = isDemoMode ? pollLatest : wsSensors
  return (
    <div className="grid grid-cols-2 gap-3">
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

// ── Detail Panel ──────────────────────────────────────────────────────────

function DetailPanel({ session, sparkData }) {
  const [tab, setTab] = useState('attendance')

  useEffect(() => setTab('attendance'), [session?.id])

  if (!session) return (
    <div className="flex flex-col items-center justify-center h-full gap-3 text-gray-600">
      <p className="text-4xl">←</p>
      <p className="text-sm">Select a session from the left to view details</p>
    </div>
  )

  return (
    <div className="flex flex-col h-full">
      {/* Session header */}
      <div className="px-5 py-4 border-b border-gray-800 shrink-0">
        <div className="flex items-center gap-2.5 mb-0.5">
          <p className="text-base font-semibold text-white">
            {session.course_name || session.course?.name}
          </p>
          <StatusBadge ds={session.display_status} />
        </div>
        <p className="text-xs text-gray-500">
          {session.course_code || session.course?.code} · Room {session.room_id} ·{' '}
          {fmtDate(session.started_at)} {fmt(session.started_at)}
          {session.ended_at ? `–${fmt(session.ended_at)}` : ''}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-800 shrink-0">
        {['attendance', 'sensors'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-5 py-3 text-sm font-medium capitalize transition-colors ${
              tab === t
                ? 'text-white border-b-2 border-indigo-500'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto px-5 py-4">
        {tab === 'attendance'
          ? (
            <AttendanceTab
              key={session.id}
              sessionId={session.id}
              isLive={session.display_status === 'live'}
            />
          )
          : (
            <SensorsTab
              key={session.id}
              sessionId={session.id}
              displayStatus={session.display_status}
              sparkData={sparkData}
            />
          )
        }
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { sensors: wsSensors, isDemoMode, isConnected } = useSensor()

  const [sessions,    setSessions]    = useState([])
  const [selectedId,  setSelectedId]  = useState(null)
  const [loadingSess, setLoadingSess] = useState(true)
  const [sessError,   setSessError]   = useState(null)

  // Sparkline rolling history (ref for accumulation, state for renders)
  const sparkRef      = useRef({ temperature: [], humidity: [], air_quality: [], sound: [] })
  const [sparkData,   setSparkData]   = useState(sparkRef.current)
  const lastPushedRef = useRef({})

  // Load session list and auto-select
  useEffect(() => {
    setLoadingSess(true)
    getSessions()
      .then(data => {
        setSessions(data)
        // Auto-select: first live → first upcoming → none
        const live     = data.find(s => s.display_status === 'live')
        const upcoming = data.find(s => s.display_status === 'upcoming')
        const pick     = live ?? upcoming ?? null
        if (pick) setSelectedId(pick.id)
      })
      .catch(() => setSessError('Could not load sessions'))
      .finally(() => setLoadingSess(false))
  }, [])

  // Accumulate WS sensor data into sparkline history
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
    <div className="flex h-screen overflow-hidden">
      {/* ── Left panel: session list ─────────────────────────────────── */}
      <div className="w-72 shrink-0 border-r border-gray-800 flex flex-col overflow-hidden">

        <div className="px-4 py-4 border-b border-gray-800 shrink-0">
          <div className="flex items-center justify-between">
            <h1 className="text-sm font-bold text-white">Sessions</h1>
            {sessions.length > 0 && (
              <span className="text-[10px] bg-gray-700 text-gray-400 px-2 py-0.5 rounded-full">
                {sessions.length} total
              </span>
            )}
          </div>
          <p className="text-[10px] text-gray-500 mt-0.5">
            {isConnected
              ? <span className="text-green-500">● Connected</span>
              : <span className="text-gray-600">○ Offline</span>}
          </p>
        </div>

        <DemoModeBanner isDemoMode={isDemoMode} />

        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-5">
          {loadingSess ? (
            <p className="text-gray-500 text-xs text-center pt-6">Loading sessions…</p>
          ) : sessError ? (
            <p className="text-red-400 text-xs text-center pt-6">{sessError}</p>
          ) : sessions.length === 0 ? (
            <p className="text-gray-600 text-xs text-center pt-6">No sessions found</p>
          ) : (
            <>
              <SessionGroup title="Live now"  sessions={live}     selectedId={selectedId} onSelect={setSelectedId} />
              <SessionGroup title="Upcoming"  sessions={upcoming} selectedId={selectedId} onSelect={setSelectedId} />
              <SessionGroup title="Past"      sessions={done}     selectedId={selectedId} onSelect={setSelectedId} />
            </>
          )}
        </div>
      </div>

      {/* ── Right panel: detail ──────────────────────────────────────── */}
      <div className="flex-1 bg-gray-900/40 overflow-hidden">
        <DetailPanel session={selectedSession} sparkData={sparkData} />
      </div>
    </div>
  )
}
