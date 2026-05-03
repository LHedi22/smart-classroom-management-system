import { useState, useEffect, useCallback } from 'react'
import client from '../api/client'
import { useAuth } from '../context/AuthContext'

// ── Helpers ───────────────────────────────────────────────────────────────

function formatRelativeTime(isoString) {
  if (!isoString) return '—'
  const diff = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 2) return 'just now'
  if (minutes < 60) return `${minutes} minutes ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours !== 1 ? 's' : ''} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days !== 1 ? 's' : ''} ago`
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString([], {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function rateBadgeClass(rate) {
  return rate < 0.5 ? 'status-chip-danger' : 'status-chip-warning'
}

function pct(rate) {
  return `${Math.round(rate * 100)}%`
}

// ── SVG icons ─────────────────────────────────────────────────────────────

const ChevronIcon = ({ open }) => (
  <svg
    width="14" height="14" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    style={{ transition: 'transform 0.2s', transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
  >
    <polyline points="6 9 12 15 18 9" />
  </svg>
)

const RefreshIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10" />
    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
  </svg>
)

const AllClearIcon = () => (
  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-green)' }}>
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
    <polyline points="22 4 12 14.01 9 11.01" />
  </svg>
)

// ── Skeleton loader ───────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--color-border)' }}>
      <div style={{ height: 14, width: '60%', borderRadius: 6, background: 'var(--color-border)', marginBottom: 8 }} />
      <div style={{ height: 12, width: '40%', borderRadius: 6, background: 'var(--color-border)', marginBottom: 8 }} />
      <div style={{ height: 12, width: '30%', borderRadius: 4, background: 'rgba(220,0,0,0.1)' }} />
    </div>
  )
}

// ── Student list card ─────────────────────────────────────────────────────

function StudentCard({ student, selected, onClick }) {
  const isSelected = selected?.student_id === student.student_id
  return (
    <button
      onClick={onClick}
      style={{
        display: 'block', width: '100%', textAlign: 'left',
        padding: '14px 16px',
        borderBottom: '1px solid var(--color-border)',
        background: isSelected ? 'rgba(0,117,201,0.06)' : 'transparent',
        borderLeft: isSelected ? '3px solid var(--color-primary)' : '3px solid transparent',
        cursor: 'pointer',
        transition: 'background 0.15s',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{
            fontFamily: "'DM Sans', sans-serif", fontWeight: 600,
            fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {student.student_name}
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginTop: 2 }}>
            {student.student_number}
          </div>
        </div>
        <span className={rateBadgeClass(student.overall_attendance_rate)}>
          {pct(student.overall_attendance_rate)}
        </span>
      </div>
      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginTop: 6 }}>
        Updated {formatRelativeTime(student.generated_at)}
      </div>
    </button>
  )
}

// ── Course accordion card ─────────────────────────────────────────────────

function CourseAccordion({ course }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="card-tight" style={{ padding: 0, marginBottom: 10 }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          width: '100%', padding: '12px 16px', background: 'none',
          border: 'none', cursor: 'pointer', gap: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
          <span className="status-chip-neutral" style={{ fontFamily: 'monospace', fontWeight: 700 }}>
            {course.course_code}
          </span>
          <span style={{
            fontSize: 'var(--text-sm)', fontWeight: 500,
            color: 'var(--color-text-primary)',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {course.course_name}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <span className={rateBadgeClass(course.attendance_rate)}>
            {pct(course.attendance_rate)}
          </span>
          <span style={{ color: 'var(--color-text-muted)' }}>
            <ChevronIcon open={open} />
          </span>
        </div>
      </button>

      {open && (
        <div style={{ padding: '0 16px 16px', borderTop: '1px solid var(--color-border)' }}>
          {/* Stats grid */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)',
            gap: 12, marginTop: 12, marginBottom: 14,
          }}>
            {[
              ['Sessions Total', course.sessions_total],
              ['Sessions Missed', course.sessions_missed],
              ['Avg Temp (missed days)', course.avg_temp_on_missed != null ? `${course.avg_temp_on_missed}°C` : '—'],
              ['Avg Air Quality (missed days)', course.avg_aq_on_missed != null ? `${course.avg_aq_on_missed} ppm` : '—'],
            ].map(([label, val]) => (
              <div key={label} style={{
                background: 'var(--color-bg)', borderRadius: 8, padding: '10px 12px',
              }}>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginBottom: 4 }}>
                  {label}
                </div>
                <div style={{ fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                  {val}
                </div>
              </div>
            ))}
          </div>

          {/* Peer comparison */}
          {course.peer_delta != null && (
            <div style={{
              fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginBottom: 12,
            }}>
              {course.peer_delta < 0
                ? <span style={{ color: 'var(--color-red)' }}>
                    {pct(Math.abs(course.peer_delta))} below class average
                  </span>
                : <span style={{ color: 'var(--color-forest)' }}>
                    {pct(course.peer_delta)} above class average
                  </span>
              }
            </div>
          )}

          {/* Per-course AI text is folded into the overall summary above */}
        </div>
      )}
    </div>
  )
}

// ── Detail panel ──────────────────────────────────────────────────────────

function DetailPanel({ studentId, isAdmin, onRecompute, recomputing }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!studentId) { setDetail(null); return }
    setLoading(true)
    client.get(`/at-risk/${studentId}`)
      .then(r => setDetail(r.data))
      .catch(() => setDetail(null))
      .finally(() => setLoading(false))
  }, [studentId])

  if (!studentId) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        height: '100%', color: 'var(--color-text-muted)', gap: 12,
      }}>
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
        <span style={{ fontSize: 'var(--text-sm)' }}>Select a student to view their explanation</span>
      </div>
    )
  }

  if (loading || !detail) {
    return (
      <div style={{ padding: 24 }}>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ height: 80, borderRadius: 10, background: 'var(--color-border)', marginBottom: 14 }} />
        ))}
      </div>
    )
  }

  return (
    <div style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <h2 style={{
            fontFamily: "'DM Sans', sans-serif", fontWeight: 700,
            fontSize: 'var(--text-xl)', color: 'var(--color-text-primary)', margin: 0,
          }}>
            {detail.student_name}
          </h2>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)', marginTop: 4 }}>
            {detail.student_number}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            className={rateBadgeClass(detail.overall_attendance_rate)}
            style={{ fontSize: 'var(--text-base)', padding: '6px 14px' }}
          >
            {pct(detail.overall_attendance_rate)} overall
          </span>
          {isAdmin && (
            <button
              className="btn-secondary"
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              onClick={onRecompute}
              disabled={recomputing}
            >
              <RefreshIcon />
              {recomputing ? 'Starting…' : 'Recompute Now'}
            </button>
          )}
        </div>
      </div>

      {/* Summary card */}
      <div className="glass-card" style={{ marginBottom: 20 }}>
        <div style={{
          fontSize: 'var(--text-xs)', fontWeight: 700, letterSpacing: '0.08em',
          textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 12,
        }}>
          Overall Pattern
        </div>

        {!detail.generated_at ? (
          <div style={{
            background: 'rgba(0,117,201,0.06)', border: '1px solid rgba(0,117,201,0.2)',
            borderRadius: 8, padding: '12px 16px',
            fontSize: 'var(--text-sm)', color: 'var(--color-primary)', lineHeight: 1.7,
          }}>
            Generating AI explanation… this page will refresh automatically.
          </div>
        ) : !detail.ollama_reachable ? (
          <div style={{
            background: 'rgba(255,183,0,0.1)', border: '1px solid rgba(255,183,0,0.3)',
            borderRadius: 8, padding: '12px 16px',
            fontSize: 'var(--text-sm)', color: '#7A5B00', lineHeight: 1.7,
          }}>
            AI explanation unavailable — the Ollama LLM service was unreachable when this
            student was last processed. Verify that the Ollama container is running and that
            the <code style={{ fontFamily: 'monospace', fontSize: '0.9em' }}>phi3:mini</code> model
            has been pulled (<code style={{ fontFamily: 'monospace', fontSize: '0.9em' }}>docker compose exec ollama ollama pull phi3:mini</code>).
            {isAdmin
              ? ' Use the Recompute Now button above to retry immediately.'
              : ' The pipeline will retry automatically after the cooldown period.'}
          </div>
        ) : (
          <p style={{
            fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)',
            lineHeight: 1.8, margin: 0,
          }}>
            {detail.summary_explanation}
          </p>
        )}
      </div>

      {/* Per-course breakdown */}
      <div style={{
        fontFamily: "'DM Sans', sans-serif", fontWeight: 600,
        fontSize: 'var(--text-sm)', color: 'var(--color-text-primary)', marginBottom: 12,
      }}>
        Course Breakdown
      </div>

      {detail.per_course_data.length === 0 ? (
        <div style={{
          fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)',
          padding: '12px 0',
        }}>
          {detail.generated_at
            ? 'No course breakdown available.'
            : 'Course breakdown will appear once the explanation has been generated.'}
        </div>
      ) : (
        detail.per_course_data.map(course => (
          <CourseAccordion key={course.course_id} course={course} />
        ))
      )}

      {/* Footer */}
      <div style={{
        marginTop: 20, fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)',
        borderTop: '1px solid var(--color-border)', paddingTop: 12,
      }}>
        {detail.generated_at
          ? `Last updated: ${fmtDate(detail.generated_at)}`
          : 'Explanation generating — this page refreshes automatically'}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function AtRisk() {
  const { professor } = useAuth()
  const isAdmin = professor?.role === 'admin'

  const [students, setStudents] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [recomputing, setRecomputing] = useState(false)

  const fetchList = useCallback(() => {
    setLoading(true)
    client.get('/at-risk')
      .then(r => setStudents(r.data))
      .catch(() => setStudents([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { fetchList() }, [fetchList])

  // Auto-poll every 8s while any student is still awaiting an AI explanation
  useEffect(() => {
    if (loading) return
    const pending = students.some(s => !s.generated_at)
    if (!pending) return
    const timer = setTimeout(fetchList, 8000)
    return () => clearTimeout(timer)
  }, [students, loading, fetchList])

  async function handleRecompute() {
    setRecomputing(true)
    try {
      await client.post('/at-risk/recompute')
    } catch {
      // swallow — 202 accepted
    }
    setTimeout(() => {
      fetchList()
      setSelected(s => s ? { ...s } : s)
      setRecomputing(false)
    }, 3000)
  }

  return (
    <div style={{ display: 'flex', height: '100%', gap: 20 }}>
      {/* ── Left panel ── */}
      <div className="glass-panel" style={{ width: 320, display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0 }}>
        <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{
              fontFamily: "'DM Sans', sans-serif", fontWeight: 700,
              fontSize: 'var(--text-base)', color: 'var(--color-text-primary)',
            }}>
              At-Risk Students
            </div>
            {!loading && (
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginTop: 2 }}>
                {students.length} flagged
              </div>
            )}
          </div>
          <button
            className="btn-secondary"
            style={{ padding: '6px 10px', fontSize: 12 }}
            onClick={fetchList}
          >
            Refresh
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {loading ? (
            [1, 2, 3].map(i => <SkeletonCard key={i} />)
          ) : students.length === 0 ? (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', height: '100%', gap: 14, padding: 24,
              color: 'var(--color-text-muted)', textAlign: 'center',
            }}>
              <AllClearIcon />
              <span style={{ fontSize: 'var(--text-sm)' }}>All students are on track</span>
            </div>
          ) : (
            students.map(s => (
              <StudentCard
                key={s.student_id}
                student={s}
                selected={selected}
                onClick={() => setSelected(s)}
              />
            ))
          )}
        </div>
      </div>

      {/* ── Right panel ── */}
      <div className="glass-panel" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <DetailPanel
          studentId={selected?.student_id}
          isAdmin={isAdmin}
          onRecompute={handleRecompute}
          recomputing={recomputing}
        />
      </div>
    </div>
  )
}
