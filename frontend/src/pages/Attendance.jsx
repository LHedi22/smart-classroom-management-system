import { useState, useEffect } from 'react'
import client from '../api/client'

const STATUS_COLORS = {
  present: 'bg-green-900 text-green-300',
  absent:  'bg-gray-700  text-gray-300',
  late:    'bg-yellow-900 text-yellow-300',
  excused: 'bg-blue-900  text-blue-300',
}

function fmt(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function exportCsv(records, sessionId) {
  const header = 'Student Name,Student ID,Status,Detected At,Adjusted By\n'
  const rows = records.map(r =>
    `"${r.student_name}","${r.student_number}","${r.status}","${r.detected_at ?? ''}","${r.adjusted_by ?? ''}"`
  ).join('\n')
  const blob = new Blob([header + rows], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `attendance_${sessionId}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export default function Attendance() {
  const [sessions, setSessions]     = useState([])
  const [sessionId, setSessionId]   = useState('')
  const [records, setRecords]       = useState([])
  const [editingId, setEditingId]   = useState(null)
  const [loading, setLoading]       = useState(false)

  useEffect(() => {
    client.get('/sessions').then(r => {
      setSessions(r.data)
      if (r.data.length > 0) setSessionId(r.data[0].id)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!sessionId) return
    setLoading(true)
    client.get(`/sessions/${sessionId}/attendance`)
      .then(r => setRecords(r.data))
      .catch(() => setRecords([]))
      .finally(() => setLoading(false))
  }, [sessionId])

  async function updateStatus(recordId, status) {
    setEditingId(null)
    setRecords(prev => prev.map(r => r.id === recordId ? { ...r, status, adjusted_by: 'professor' } : r))
    await client.patch(`/attendance/${recordId}`, { status })
  }

  async function markAllAbsent() {
    if (!sessionId) return
    await client.post(`/sessions/${sessionId}/mark-absent`)
    const r = await client.get(`/sessions/${sessionId}/attendance`)
    setRecords(r.data)
  }

  const session = sessions.find(s => s.id === sessionId)

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">Attendance</h1>
        <div className="flex items-center gap-3">
          <select
            value={sessionId}
            onChange={e => setSessionId(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-indigo-500"
          >
            {sessions.map(s => (
              <option key={s.id} value={s.id}>
                {s.course?.code ?? 'Session'} — {new Date(s.started_at).toLocaleDateString()}
                {s.status === 'active' ? ' (live)' : ''}
              </option>
            ))}
          </select>
          <button
            onClick={markAllAbsent}
            className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg"
          >
            Mark absent
          </button>
          <button
            onClick={() => exportCsv(records, sessionId)}
            className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg"
          >
            Export CSV
          </button>
        </div>
      </div>

      {session && (
        <div className="flex gap-4 text-sm text-gray-400">
          <span>Course: <span className="text-white">{session.course?.name ?? '—'}</span></span>
          <span>Present: <span className="text-green-400">{session.present_count}</span></span>
          <span>Total: <span className="text-white">{session.total_students}</span></span>
          <span className={`ml-auto px-2 py-0.5 rounded text-xs font-medium ${
            session.status === 'active' ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-300'
          }`}>{session.status}</span>
        </div>
      )}

      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-40 text-gray-500 text-sm">Loading…</div>
        ) : records.length === 0 ? (
          <div className="flex items-center justify-center h-40 text-gray-600 text-sm">No records</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-gray-800">
                <th className="text-left px-4 py-3 font-medium">Student Name</th>
                <th className="text-left px-4 py-3 font-medium">Student ID</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Detected At</th>
                <th className="text-left px-4 py-3 font-medium">Note</th>
              </tr>
            </thead>
            <tbody>
              {records.map(rec => (
                <tr key={rec.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="px-4 py-2.5 text-white font-medium">{rec.student_name}</td>
                  <td className="px-4 py-2.5 text-gray-400 font-mono text-xs">{rec.student_number}</td>
                  <td className="px-4 py-2.5">
                    {editingId === rec.id ? (
                      <select
                        autoFocus
                        defaultValue={rec.status}
                        onChange={e => updateStatus(rec.id, e.target.value)}
                        onBlur={() => setEditingId(null)}
                        className="bg-gray-700 text-white text-xs rounded px-2 py-1 focus:outline-none"
                      >
                        {['present', 'absent', 'late', 'excused'].map(s => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    ) : (
                      <button
                        onClick={() => setEditingId(rec.id)}
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[rec.status]}`}
                      >
                        {rec.status}
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-gray-400 text-xs">{fmt(rec.detected_at)}</td>
                  <td className="px-4 py-2.5 text-xs">
                    {rec.adjusted_by && (
                      <span className="text-yellow-500">Adjusted by professor</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
