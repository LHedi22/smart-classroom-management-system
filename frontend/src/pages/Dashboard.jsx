import { useState, useEffect } from 'react'
import { useSensor } from '../context/SensorContext'
import client from '../api/client'

// ── helpers ───────────────────────────────────────────────────────────────

function timeAgo(iso) {
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

const STATUS_COLORS = {
  present: 'bg-green-900 text-green-300',
  absent:  'bg-gray-700 text-gray-300',
  late:    'bg-yellow-900 text-yellow-300',
  excused: 'bg-blue-900 text-blue-300',
}

const ALERT_ICONS = {
  temp_high:         '🌡',
  temp_low:          '❄',
  air_quality_high:  '💨',
  attendance_anomaly:'⚠',
  device_offline:    '📡',
}

// ── sub-components ────────────────────────────────────────────────────────

function SensorCard({ label, main, sub, accent }) {
  return (
    <div className={`bg-gray-800 rounded-xl p-4 border-l-4 ${accent}`}>
      <p className="text-xs text-gray-400 uppercase tracking-widest mb-1">{label}</p>
      <p className="text-3xl font-bold text-white">{main ?? '—'}</p>
      <p className="text-xs text-gray-400 mt-1">{sub}</p>
    </div>
  )
}

function RelayToggle({ label, value, onChange }) {
  const opts = ['on', 'off', 'auto']
  return (
    <div>
      <p className="text-xs text-gray-400 uppercase tracking-widest mb-2">{label}</p>
      <div className="flex rounded-lg overflow-hidden border border-gray-700">
        {opts.map(opt => (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            className={`flex-1 py-1.5 text-xs font-medium capitalize transition-colors ${
              value === opt
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Start Session Modal ───────────────────────────────────────────────────

function StartSessionModal({ courses, onStart, onClose }) {
  const [courseId, setCourseId] = useState(courses[0]?.id ?? '')
  const [roomId, setRoomId]     = useState('room1')
  const [loading, setLoading]   = useState(false)

  async function submit(e) {
    e.preventDefault()
    if (!courseId) return
    setLoading(true)
    try { await onStart(courseId, roomId) } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-gray-900 rounded-2xl p-6 w-96 border border-gray-700 shadow-2xl">
        <h3 className="text-lg font-semibold text-white mb-4">Start Session</h3>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Course</label>
            <select
              value={courseId}
              onChange={e => setCourseId(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            >
              {courses.map(c => (
                <option key={c.id} value={c.id}>{c.code} — {c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Room ID</label>
            <input
              value={roomId}
              onChange={e => setRoomId(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 py-2 rounded-lg border border-gray-700 text-sm text-gray-400 hover:bg-gray-800">
              Cancel
            </button>
            <button type="submit" disabled={loading || !courseId}
              className="flex-1 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-sm text-white font-medium disabled:opacity-50">
              {loading ? 'Starting…' : 'Start'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { sensors, attendance, alerts, relayStatus, isConnected } = useSensor()

  const [courses, setCourses]           = useState([])
  const [activeSession, setActiveSession] = useState(null)
  const [showModal, setShowModal]       = useState(false)
  const [relay, setRelay]               = useState({ ac: 'auto', lighting: 'auto' })

  useEffect(() => {
    client.get('/courses').then(r => setCourses(r.data)).catch(() => {})
    client.get('/sessions?status=active').then(r => {
      if (r.data.length > 0) setActiveSession(r.data[0])
    }).catch(() => {})
  }, [])

  // Sync relay display from WebSocket snapshot
  useEffect(() => { setRelay(relayStatus) }, [relayStatus])

  async function sendRelay(device, action) {
    setRelay(prev => ({ ...prev, [device]: action }))
    await client.post(`/control/${device}`, { room_id: activeSession?.room_id ?? 'room1', action })
  }

  async function startSession(courseId, roomId) {
    const r = await client.post('/sessions/start', { course_id: courseId, room_id: roomId })
    setActiveSession(r.data)
    setShowModal(false)
  }

  async function endSession() {
    if (!activeSession) return
    await client.post(`/sessions/${activeSession.id}/end`)
    setActiveSession(null)
  }

  // Derived sensor values
  const temp = sensors.temperature?.value
  const hum  = sensors.humidity?.value
  const aq   = sensors.air_quality?.value
  const snd  = sensors.sound?.value

  const tempAccent = temp == null ? 'border-gray-700'
    : temp > 28 ? 'border-red-500'
    : temp < 22 ? 'border-blue-500'
    : 'border-green-500'

  const aqLabel = aq == null ? '—'
    : aq > 500 ? 'Poor'
    : aq > 300 ? 'Moderate'
    : 'Good'

  const aqAccent = aq == null ? 'border-gray-700'
    : aq > 500 ? 'border-red-500'
    : aq > 300 ? 'border-yellow-500'
    : 'border-green-500'

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Dashboard</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            {isConnected ? 'Live data' : 'Offline — reconnecting…'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {activeSession ? (
            <>
              <span className="text-xs bg-green-900 text-green-300 px-3 py-1.5 rounded-full font-medium">
                Session active
              </span>
              <button onClick={endSession}
                className="px-4 py-1.5 bg-red-600 hover:bg-red-500 text-white text-sm rounded-lg font-medium">
                End Session
              </button>
            </>
          ) : (
            <button onClick={() => setShowModal(true)}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg font-medium">
              + Start Session
            </button>
          )}
        </div>
      </div>

      {/* Active session banner */}
      {activeSession && (
        <div className="bg-indigo-900/40 border border-indigo-700 rounded-xl px-4 py-3 text-sm text-indigo-200">
          Active: <span className="font-medium">{activeSession.course?.name ?? activeSession.course_id}</span>
          {' '}— Room <span className="font-medium">{activeSession.room_id}</span>
          <span className="text-indigo-400 ml-3 text-xs">
            Started {timeAgo(activeSession.started_at)}
          </span>
        </div>
      )}

      <div className="grid grid-cols-12 gap-5">
        {/* ── Left: Sensor cards ─────────────────────────────────────── */}
        <div className="col-span-3 space-y-4">
          <SensorCard
            label="Temperature"
            main={temp != null ? `${temp.toFixed(1)}°C` : null}
            sub={temp == null ? 'No data' : temp > 28 ? 'High — AC recommended' : temp < 22 ? 'Low' : 'Comfortable'}
            accent={tempAccent}
          />
          <SensorCard
            label="Humidity"
            main={hum != null ? `${hum.toFixed(0)}%` : null}
            sub={hum == null ? 'No data' : hum > 70 ? 'High' : hum < 30 ? 'Low' : 'Normal'}
            accent="border-blue-500"
          />
          <SensorCard
            label="Air Quality"
            main={aq != null ? `${aq.toFixed(0)} ppm` : null}
            sub={aqLabel}
            accent={aqAccent}
          />
          <SensorCard
            label="Sound"
            main={snd != null ? (snd > 0 ? 'Active' : 'Quiet') : null}
            sub={snd != null ? (snd > 0 ? 'Activity detected' : 'No noise') : 'No data'}
            accent={snd > 0 ? 'border-yellow-500' : 'border-gray-700'}
          />
        </div>

        {/* ── Center: Attendance ─────────────────────────────────────── */}
        <div className="col-span-6">
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden h-full">
            <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">Live Attendance</h2>
              <span className="text-xs text-gray-500">{attendance.length} recognized</span>
            </div>
            {attendance.length === 0 ? (
              <div className="flex items-center justify-center h-48 text-gray-600 text-sm">
                No attendance events yet
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-gray-500 border-b border-gray-800">
                    <th className="text-left px-4 py-2 font-medium">Student</th>
                    <th className="text-left px-4 py-2 font-medium">Status</th>
                    <th className="text-left px-4 py-2 font-medium">Confidence</th>
                    <th className="text-left px-4 py-2 font-medium">Detected</th>
                  </tr>
                </thead>
                <tbody>
                  {attendance.map((rec, i) => (
                    <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                      <td className="px-4 py-2.5 text-white font-medium">
                        {rec.student_name ?? rec.student_id}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[rec.status] ?? STATUS_COLORS.present}`}>
                          {rec.status}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-gray-400 text-xs">
                        {rec.confidence != null ? `${(rec.confidence * 100).toFixed(0)}%` : '—'}
                      </td>
                      <td className="px-4 py-2.5 text-gray-400 text-xs">
                        {timeAgo(rec.detected_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* ── Right: Controls + Alerts ───────────────────────────────── */}
        <div className="col-span-3 space-y-4">
          {/* Relay controls */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 space-y-4">
            <h2 className="text-sm font-semibold text-white">Controls</h2>
            <RelayToggle label="AC" value={relay.ac}
              onChange={v => sendRelay('ac', v)} />
            <RelayToggle label="Lighting" value={relay.lighting}
              onChange={v => sendRelay('lighting', v)} />
          </div>

          {/* Alert feed */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">Recent Alerts</h2>
              {alerts.length > 0 && (
                <span className="text-xs bg-red-900 text-red-300 px-2 py-0.5 rounded-full">
                  {alerts.length}
                </span>
              )}
            </div>
            {alerts.length === 0 ? (
              <p className="text-gray-600 text-xs text-center py-6">No alerts</p>
            ) : (
              <div className="divide-y divide-gray-800">
                {alerts.slice(0, 5).map((a, i) => (
                  <div key={i} className="px-4 py-2.5 flex gap-2">
                    <span className="text-base leading-none shrink-0">
                      {ALERT_ICONS[a.alert_type] ?? '⚠'}
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs text-gray-200 leading-tight line-clamp-2">{a.message}</p>
                      <p className="text-[10px] text-gray-500 mt-0.5">{timeAgo(a.created_at)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {showModal && (
        <StartSessionModal
          courses={courses}
          onStart={startSession}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  )
}
