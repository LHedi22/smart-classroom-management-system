import { useState, useEffect } from 'react'
import client from '../api/client'

const STATUS_CLASSES = {
  present: 'status-chip-success',
  absent:  'status-chip-danger',
  late:    'status-chip-warning',
  excused: 'status-chip-neutral',
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

// ── Stat pill ─────────────────────────────────────────────────────────────

function StatPill({ label, value, valueColor }) {
  return (
    <div style={{
      borderRadius: 10,
      border: '1px solid var(--color-border)',
      background: 'var(--color-surface)',
      padding: '10px 16px',
    }}>
      <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>{label}</p>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 20, fontWeight: 700, color: valueColor ?? 'var(--color-text-primary)', letterSpacing: '-0.02em' }}>{value}</p>
    </div>
  )
}

// ── Empty chair SVG ───────────────────────────────────────────────────────

function EmptyChairSVG() {
  return (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="10" y="20" width="44" height="6" rx="3" fill="var(--color-border)" />
      <rect x="18" y="26" width="28" height="22" rx="4" fill="rgba(221,227,237,0.6)" stroke="var(--color-border)" strokeWidth="1.5"/>
      <rect x="14" y="48" width="6" height="10" rx="3" fill="var(--color-border)" />
      <rect x="44" y="48" width="6" height="10" rx="3" fill="var(--color-border)" />
      <rect x="12" y="10" width="40" height="12" rx="4" fill="rgba(221,227,237,0.6)" stroke="var(--color-border)" strokeWidth="1.5"/>
    </svg>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function Attendance() {
  const [sessions,      setSessions]      = useState([])
  const [sessionId,     setSessionId]     = useState('')
  const [records,       setRecords]       = useState([])
  const [editingId,     setEditingId]     = useState(null)
  const [loading,       setLoading]       = useState(false)
  const [atRiskMap,     setAtRiskMap]     = useState({}) // student_id → { attendance_rate, consecutive_absences }

  useEffect(() => {
    client.get('/insights/students/at-risk')
      .then(r => {
        const map = {}
        r.data.forEach(s => { map[s.student_id] = s })
        setAtRiskMap(map)
      })
      .catch(() => {})
  }, [])

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
    if (!recordId) return  // virtual record — no DB row yet
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
  const present = records.filter(r => r.status === 'present').length
  const absent  = records.filter(r => r.status === 'absent').length
  const late    = records.filter(r => r.status === 'late').length
  const total   = records.length

  return (
    <div className="page-shell">
      {/* Page header */}
      <section className="page-header-card">
        <div className="page-header-row">
          <h1 className="section-title">Attendance</h1>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={markAllAbsent} className="btn-secondary">Mark absent</button>
            <button onClick={() => exportCsv(records, sessionId)} className="btn-primary">Export CSV</button>
          </div>
        </div>

        {/* Session selector */}
        <select
          value={sessionId}
          onChange={e => setSessionId(e.target.value)}
          className="field-control"
          style={{ maxWidth: 480 }}
        >
          {sessions.map(s => (
            <option key={s.id} value={s.id}>
              {s.course?.code ?? 'Session'} — {new Date(s.started_at).toLocaleDateString()}
              {s.status === 'active' ? ' · live' : ''}
            </option>
          ))}
        </select>

        {/* Session stats */}
        {session && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 10 }}>
            <StatPill label="Course"  value={session.course?.code ?? '—'} />
            <StatPill label="Present" value={present} valueColor="var(--color-forest)" />
            <StatPill label="Absent"  value={absent}  valueColor="var(--color-red)" />
            <StatPill label="Late"    value={late}     valueColor="#7A5B00" />
            <StatPill label="Total"   value={total} />
          </div>
        )}
      </section>

      {/* Attendance table */}
      <section className="table-shell" style={{ flex: 1 }}>
        {loading ? (
          <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[1,2,3,4].map(i => <div key={i} className="skeleton" style={{ height: 44, borderRadius: 8, opacity: 0.8 - i * 0.12 }} />)}
          </div>
        ) : records.length === 0 ? (
          <div className="empty-state">
            <EmptyChairSVG />
            <p className="empty-state-title">No students enrolled</p>
            <p className="empty-state-desc">
              Enroll students in this course to see their attendance here.
            </p>
          </div>
        ) : (
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr className="table-head-row">
                <th style={{ textAlign: 'left', padding: '11px 16px' }}>Student</th>
                <th style={{ textAlign: 'left', padding: '11px 16px' }}>ID</th>
                <th style={{ textAlign: 'left', padding: '11px 16px' }}>Status</th>
                <th style={{ textAlign: 'left', padding: '11px 16px' }}>Detected at</th>
                <th style={{ textAlign: 'left', padding: '11px 16px' }}>Note</th>
              </tr>
            </thead>
            <tbody>
              {records.map(rec => {
                const riskInfo = atRiskMap[rec.student_id]
                const isAtRisk = !!riskInfo
                const isVirtual = !rec.id
                return (
                <tr key={rec.id ?? `virtual-${rec.student_id}`} className="table-row" style={{ opacity: isVirtual ? 0.72 : 1 }}>
                  <td style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
                      {rec.student_name}
                      {isAtRisk && (
                        <span className="status-chip-danger" style={{ fontSize: 10, padding: '2px 7px' }}>At Risk</span>
                      )}
                    </span>
                    {isAtRisk && (riskInfo.consecutive_absences ?? 0) >= 2 && (
                      <span style={{ display: 'block', fontSize: 10, color: 'var(--color-text-muted)', fontWeight: 400, marginTop: 2 }}>
                        absent {riskInfo.consecutive_absences}×
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--color-text-muted)', fontFamily: 'monospace', fontSize: 12 }}>{rec.student_number}</td>
                  <td style={{ padding: '12px 16px' }}>
                    {!isVirtual && editingId === rec.id ? (
                      <select
                        autoFocus
                        defaultValue={rec.status}
                        onChange={e => updateStatus(rec.id, e.target.value)}
                        onBlur={() => setEditingId(null)}
                        className="field-control-sm"
                      >
                        {['present', 'absent', 'late', 'excused'].map(s => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    ) : (
                      <button
                        title={isVirtual ? 'Not yet detected — click "Mark absent" to record' : 'Click to edit'}
                        onClick={() => !isVirtual && setEditingId(rec.id)}
                        className={STATUS_CLASSES[rec.status]}
                        style={{
                          cursor: isVirtual ? 'default' : 'pointer',
                          border: 'none',
                          background: 'inherit',
                          font: 'inherit',
                          padding: 'inherit',
                          borderRadius: 'inherit',
                          transition: 'opacity 0.15s',
                        }}
                      >
                        {rec.status}
                      </button>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--color-text-muted)', fontSize: 12 }}>
                    {isVirtual
                      ? <span style={{ fontStyle: 'italic', fontSize: 11 }}>not detected</span>
                      : fmt(rec.detected_at)
                    }
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: 12 }}>
                    {rec.adjusted_by && (
                      <span style={{ color: '#7A5B00', fontWeight: 600, fontSize: 11 }}>Adjusted by professor</span>
                    )}
                  </td>
                </tr>
              )})}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
