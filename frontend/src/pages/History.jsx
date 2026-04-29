import { Fragment, useState, useEffect } from 'react'
import client from '../api/client'

function duration(start, end) {
  if (!start || !end) return '—'
  const mins = Math.round((new Date(end) - new Date(start)) / 60_000)
  if (mins < 60) return `${mins}m`
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}

// ── SVG icons ─────────────────────────────────────────────────────────────

const ChevronIcon = ({ expanded }) => (
  <svg
    width="14" height="14" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
    style={{ transition: 'transform 0.2s ease', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}
  >
    <polyline points="9 18 15 12 9 6"/>
  </svg>
)

const SyncIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="1 4 1 10 7 10"/>
    <polyline points="23 20 23 14 17 14"/>
    <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/>
  </svg>
)

const CheckIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12"/>
  </svg>
)

const ClockHistoryIcon = () => (
  <svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/>
    <polyline points="12 6 12 12 16 14"/>
  </svg>
)

// ── Attendance breakdown bar ───────────────────────────────────────────────

function AttendanceBar({ records }) {
  if (!records || records.length === 0) return null
  const total   = records.length
  const present = records.filter(r => r.status === 'present').length
  const late    = records.filter(r => r.status === 'late').length
  const absent  = records.filter(r => r.status === 'absent').length
  const excused = records.filter(r => r.status === 'excused').length

  const pctP = (present / total) * 100
  const pctL = (late    / total) * 100
  const pctA = (absent  / total) * 100
  const pctE = (excused / total) * 100

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', gap: 16, marginBottom: 8 }}>
        {[
          { label: 'Present', count: present, color: 'var(--color-forest)' },
          { label: 'Late',    count: late,    color: '#7A5B00' },
          { label: 'Absent',  count: absent,  color: 'var(--color-red)' },
          { label: 'Excused', count: excused, color: 'var(--color-text-muted)' },
        ].filter(s => s.count > 0).map(s => (
          <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: s.color, flexShrink: 0 }} />
            <span style={{ fontSize: 11, color: 'var(--color-text-muted)', fontWeight: 600 }}>
              {s.label} <span style={{ color: s.color }}>{s.count}</span>
            </span>
          </div>
        ))}
      </div>
      <div style={{
        height: 8, borderRadius: 99, overflow: 'hidden',
        background: 'var(--color-border)', display: 'flex',
      }}>
        {pctP > 0 && <div style={{ width: `${pctP}%`, background: 'var(--color-green)', transition: 'width 0.4s ease' }} />}
        {pctL > 0 && <div style={{ width: `${pctL}%`, background: 'var(--color-yellow)', transition: 'width 0.4s ease' }} />}
        {pctA > 0 && <div style={{ width: `${pctA}%`, background: 'var(--color-red)', transition: 'width 0.4s ease' }} />}
        {pctE > 0 && <div style={{ width: `${pctE}%`, background: 'var(--color-border-strong)', transition: 'width 0.4s ease' }} />}
      </div>
    </div>
  )
}

// ── Status badge ──────────────────────────────────────────────────────────

const STATUS_CHIP = {
  present: 'status-chip-success',
  absent:  'status-chip-danger',
  late:    'status-chip-warning',
  excused: 'status-chip-neutral',
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function History() {
  const [sessions,   setSessions]   = useState([])
  const [expandedId, setExpandedId] = useState(null)
  const [attendance, setAttendance] = useState({})
  const [syncStatus, setSyncStatus] = useState({})
  const [loading,    setLoading]    = useState(false)
  const [courseFilter, setCourseFilter] = useState('')

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

  const courses = [...new Set(sessions.map(s => s.course?.code).filter(Boolean))]
  const filtered = courseFilter
    ? sessions.filter(s => s.course?.code === courseFilter)
    : sessions

  return (
    <div className="page-shell">
      {/* Page header */}
      <section className="page-header-card">
        <div className="page-header-row">
          <h1 className="section-title">Session History</h1>
          <span className="status-chip-neutral">{sessions.length} sessions</span>
        </div>

        {/* Filter bar */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <select
            value={courseFilter}
            onChange={e => setCourseFilter(e.target.value)}
            className="field-control"
            style={{ width: 200 }}
          >
            <option value="">All courses</option>
            {courses.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          {courseFilter && (
            <button
              onClick={() => setCourseFilter('')}
              className="btn-secondary"
              style={{ padding: '7px 14px', fontSize: 12 }}
            >
              Clear
            </button>
          )}
        </div>
      </section>

      {/* Table */}
      <section className="table-shell" style={{ flex: 1 }}>
        {loading ? (
          <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[1,2,3,4].map(i => (
              <div key={i} className="skeleton" style={{ height: 52, borderRadius: 8, opacity: 0.8 - i * 0.12 }} />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon" style={{ color: 'var(--color-text-muted)' }}>
              <ClockHistoryIcon />
            </div>
            <p className="empty-state-title">No sessions yet</p>
            <p className="empty-state-desc">
              {courseFilter ? 'No sessions for this course.' : 'Sessions appear here after they end.'}
            </p>
          </div>
        ) : (
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr className="table-head-row">
                <th style={{ textAlign: 'left', padding: '11px 16px', width: 24 }} />
                <th style={{ textAlign: 'left', padding: '11px 16px' }}>Course</th>
                <th style={{ textAlign: 'left', padding: '11px 16px' }}>Date</th>
                <th style={{ textAlign: 'left', padding: '11px 16px' }}>Duration</th>
                <th style={{ textAlign: 'left', padding: '11px 16px' }}>Attendance</th>
                <th style={{ textAlign: 'left', padding: '11px 16px' }}>Status</th>
                <th style={{ textAlign: 'left', padding: '11px 16px' }}>Moodle</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(s => {
                const pct      = s.total_students > 0
                  ? Math.round((s.present_count / s.total_students) * 100) : null
                const sync     = syncStatus[s.id]
                const isExpanded = expandedId === s.id
                const recs     = attendance[s.id] ?? []

                return (
                  <Fragment key={s.id}>
                    <tr
                      onClick={() => toggleRow(s.id)}
                      className="table-row"
                      style={{
                        cursor: 'pointer',
                        background: isExpanded ? 'rgba(0,117,201,0.03)' : undefined,
                        borderLeft: isExpanded ? '3px solid var(--color-primary)' : '3px solid transparent',
                      }}
                    >
                      {/* Chevron */}
                      <td style={{ padding: '12px 8px 12px 16px', color: 'var(--color-text-muted)', width: 24 }}>
                        <ChevronIcon expanded={isExpanded} />
                      </td>

                      {/* Course */}
                      <td style={{ padding: '12px 16px' }}>
                        <p style={{ fontWeight: 700, color: 'var(--color-text-primary)', fontSize: 13 }}>
                          {s.course?.name ?? '—'}
                        </p>
                        <p style={{ fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'monospace', marginTop: 2 }}>
                          {s.course?.code}
                        </p>
                      </td>

                      {/* Date */}
                      <td style={{ padding: '12px 16px' }}>
                        <p style={{ color: 'var(--color-text-primary)', fontWeight: 600 }}>
                          {new Date(s.started_at).toLocaleDateString()}
                        </p>
                        <p style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2 }}>
                          {new Date(s.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </p>
                      </td>

                      {/* Duration */}
                      <td style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontSize: 12, fontFamily: 'monospace' }}>
                        {duration(s.started_at, s.ended_at)}
                      </td>

                      {/* Attendance bar */}
                      <td style={{ padding: '12px 16px', minWidth: 140 }}>
                        {pct != null ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <div style={{ flex: 1, height: 6, borderRadius: 99, background: 'var(--color-border)', overflow: 'hidden' }}>
                              <div style={{
                                height: '100%',
                                width: `${pct}%`,
                                background: pct >= 70 ? 'var(--color-green)' : pct >= 50 ? 'var(--color-yellow)' : 'var(--color-red)',
                                borderRadius: 99,
                                transition: 'width 0.4s ease',
                              }} />
                            </div>
                            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-text-secondary)', width: 32, flexShrink: 0 }}>
                              {pct}%
                            </span>
                          </div>
                        ) : (
                          <span style={{ color: 'var(--color-text-muted)' }}>—</span>
                        )}
                      </td>

                      {/* Status */}
                      <td style={{ padding: '12px 16px' }}>
                        <span className={s.status === 'active' ? 'status-chip-success' : 'status-chip-neutral'}>
                          {s.status}
                        </span>
                      </td>

                      {/* Moodle sync */}
                      <td style={{ padding: '12px 16px' }}>
                        {sync === 'ok' ? (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--color-forest)', fontWeight: 600, fontSize: 12 }}>
                            <CheckIcon /> Synced
                          </span>
                        ) : sync === 'syncing' ? (
                          <span style={{ color: 'var(--color-text-muted)', fontSize: 12 }}>Syncing…</span>
                        ) : sync === 'error' ? (
                          <span style={{ color: 'var(--color-red)', fontWeight: 600, fontSize: 12 }}>Error</span>
                        ) : sync === 'partial' ? (
                          <span style={{ color: 'var(--color-yellow)', fontWeight: 600, fontSize: 12 }}>Partial</span>
                        ) : (
                          <button
                            onClick={e => syncMoodle(s.id, e)}
                            className="btn-secondary"
                            style={{ padding: '5px 10px', fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 5 }}
                          >
                            <SyncIcon /> Sync
                          </button>
                        )}
                      </td>
                    </tr>

                    {/* Expanded row */}
                    {isExpanded && (
                      <tr>
                        <td colSpan={7} style={{ padding: 0, borderBottom: '1px solid var(--color-border)' }}>
                          <div style={{
                            padding: '20px 24px 20px 40px',
                            background: 'rgba(0,117,201,0.02)',
                            borderTop: '1px solid var(--color-border)',
                          }}>
                            {recs.length === 0 ? (
                              <p style={{ textAlign: 'center', color: 'var(--color-text-muted)', fontSize: 13, padding: '12px 0' }}>
                                No attendance records for this session.
                              </p>
                            ) : (
                              <>
                                <AttendanceBar records={recs} />
                                <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                                  <thead>
                                    <tr style={{ color: 'var(--color-text-muted)' }}>
                                      <th style={{ textAlign: 'left', paddingBottom: 8, fontWeight: 600 }}>Student</th>
                                      <th style={{ textAlign: 'left', paddingBottom: 8, fontWeight: 600 }}>ID</th>
                                      <th style={{ textAlign: 'left', paddingBottom: 8, fontWeight: 600 }}>Status</th>
                                      <th style={{ textAlign: 'left', paddingBottom: 8, fontWeight: 600 }}>Detected</th>
                                      <th style={{ textAlign: 'left', paddingBottom: 8, fontWeight: 600 }}>Moodle</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {recs.map(r => (
                                      <tr key={r.id} style={{ borderTop: '1px solid var(--color-border)' }}>
                                        <td style={{ padding: '9px 0', fontWeight: 600, color: 'var(--color-text-primary)' }}>{r.student_name}</td>
                                        <td style={{ padding: '9px 0', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>{r.student_number}</td>
                                        <td style={{ padding: '9px 0' }}>
                                          <span className={STATUS_CHIP[r.status]}>{r.status}</span>
                                        </td>
                                        <td style={{ padding: '9px 0', color: 'var(--color-text-muted)' }}>
                                          {r.detected_at
                                            ? new Date(r.detected_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                                            : '—'}
                                        </td>
                                        <td style={{ padding: '9px 0' }}>
                                          {r.moodle_synced
                                            ? <span style={{ color: 'var(--color-forest)', fontWeight: 600 }}>Yes</span>
                                            : <span style={{ color: 'var(--color-text-muted)' }}>—</span>}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
