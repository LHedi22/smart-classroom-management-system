import { Fragment, useState, useEffect } from 'react'
import client from '../api/client'

const STATUS_COLORS = {
  present: 'text-green-400',
  absent:  'text-gray-400',
  late:    'text-yellow-400',
  excused: 'text-blue-400',
}

function duration(start, end) {
  if (!start || !end) return '—'
  const mins = Math.round((new Date(end) - new Date(start)) / 60_000)
  if (mins < 60) return `${mins}m`
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}

export default function History() {
  const [sessions, setSessions]   = useState([])
  const [expandedId, setExpandedId] = useState(null)
  const [attendance, setAttendance] = useState({})
  const [syncStatus, setSyncStatus] = useState({})
  const [loading, setLoading]       = useState(false)

  useEffect(() => {
    setLoading(true)
    client.get('/sessions').then(r => setSessions(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  async function toggleRow(sid) {
    if (expandedId === sid) { setExpandedId(null); return }
    setExpandedId(sid)
    if (!attendance[sid]) {
      const r = await client.get(`/sessions/${sid}/attendance`)
      setAttendance(prev => ({ ...prev, [sid]: r.data }))
    }
  }

  async function syncMoodle(sid, e) {
    e.stopPropagation()
    setSyncStatus(prev => ({ ...prev, [sid]: 'syncing' }))
    try {
      const r = await client.post(`/sessions/${sid}/sync-moodle`)
      setSyncStatus(prev => ({ ...prev, [sid]: r.data.failed === 0 ? 'ok' : 'partial' }))
    } catch {
      setSyncStatus(prev => ({ ...prev, [sid]: 'error' }))
    }
  }

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-xl font-bold text-white">Session History</h1>

      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-40 text-gray-500 text-sm">Loading…</div>
        ) : sessions.length === 0 ? (
          <div className="flex items-center justify-center h-40 text-gray-600 text-sm">No sessions</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-gray-800">
                <th className="text-left px-4 py-3 font-medium">Course</th>
                <th className="text-left px-4 py-3 font-medium">Date</th>
                <th className="text-left px-4 py-3 font-medium">Duration</th>
                <th className="text-left px-4 py-3 font-medium">Present %</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Moodle</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => {
                const pct = s.total_students > 0
                  ? Math.round((s.present_count / s.total_students) * 100)
                  : null
                const sync = syncStatus[s.id]
                const isExpanded = expandedId === s.id
                const recs = attendance[s.id] ?? []

                return (
                  <Fragment key={s.id}>
                    <tr
                      onClick={() => toggleRow(s.id)}
                      className={`border-b border-gray-800/50 cursor-pointer hover:bg-gray-800/30 transition-colors ${
                        isExpanded ? 'bg-gray-800/20' : ''
                      }`}
                    >
                      <td className="px-4 py-3 text-white font-medium">
                        <div>{s.course?.name ?? '—'}</div>
                        <div className="text-xs text-gray-500 font-mono">{s.course?.code}</div>
                      </td>
                      <td className="px-4 py-3 text-gray-300">
                        {new Date(s.started_at).toLocaleDateString()}
                        <div className="text-xs text-gray-500">
                          {new Date(s.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-300">{duration(s.started_at, s.ended_at)}</td>
                      <td className="px-4 py-3">
                        {pct != null ? (
                          <div className="flex items-center gap-2">
                            <div className="w-20 bg-gray-700 rounded-full h-1.5">
                              <div
                                className={`h-1.5 rounded-full ${pct >= 70 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                            <span className="text-gray-300 text-xs">{pct}%</span>
                          </div>
                        ) : (
                          <span className="text-gray-600">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          s.status === 'active' ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-400'
                        }`}>{s.status}</span>
                      </td>
                      <td className="px-4 py-3">
                        {sync === 'ok' ? (
                          <span className="text-green-400 text-xs">Synced ✓</span>
                        ) : sync === 'syncing' ? (
                          <span className="text-gray-400 text-xs">Syncing…</span>
                        ) : sync === 'error' ? (
                          <span className="text-red-400 text-xs">Error</span>
                        ) : (
                          <button
                            onClick={e => syncMoodle(s.id, e)}
                            className="text-xs px-2 py-1 bg-indigo-900 hover:bg-indigo-800 text-indigo-300 rounded font-medium"
                          >
                            Sync
                          </button>
                        )}
                      </td>
                    </tr>

                    {isExpanded && (
                      <tr>
                        <td colSpan={6} className="px-6 py-4 bg-gray-950 border-b border-gray-800">
                          {recs.length === 0 ? (
                            <p className="text-gray-600 text-sm text-center py-2">No attendance records</p>
                          ) : (
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="text-gray-500">
                                  <th className="text-left py-1.5 font-medium">Student</th>
                                  <th className="text-left py-1.5 font-medium">ID</th>
                                  <th className="text-left py-1.5 font-medium">Status</th>
                                  <th className="text-left py-1.5 font-medium">Detected</th>
                                  <th className="text-left py-1.5 font-medium">Moodle</th>
                                </tr>
                              </thead>
                              <tbody>
                                {recs.map(r => (
                                  <tr key={r.id} className="border-t border-gray-800">
                                    <td className="py-1.5 text-gray-200">{r.student_name}</td>
                                    <td className="py-1.5 text-gray-500 font-mono">{r.student_number}</td>
                                    <td className="py-1.5">
                                      <span className={`font-medium ${STATUS_COLORS[r.status]}`}>{r.status}</span>
                                    </td>
                                    <td className="py-1.5 text-gray-500">
                                      {r.detected_at
                                        ? new Date(r.detected_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                                        : '—'}
                                    </td>
                                    <td className="py-1.5">
                                      {r.moodle_synced
                                        ? <span className="text-green-500">✓</span>
                                        : <span className="text-gray-600">—</span>}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
