import { useState, useEffect, useCallback } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
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

function pct(rate) {
  return `${Math.round(rate * 100)}%`
}

// ── Classification helpers ────────────────────────────────────────────────

const CLASSIFICATION_BADGE = {
  accelerating_decline: 'status-chip-danger',
  steady_decline:       'status-chip-warning',
  stable:               'status-chip-neutral',
  recovering:           'status-chip-success',
}

const CLASSIFICATION_LABEL = {
  accelerating_decline: 'Accelerating Decline',
  steady_decline:       'Steady Decline',
  stable:               'Stable',
  recovering:           'Recovering',
}

const ACTION_CONFIG = {
  consider_intervention: {
    bg: 'rgba(236,0,68,0.08)', border: 'rgba(236,0,68,0.2)',
    color: 'var(--color-red)', label: 'Intervention Recommended',
  },
  monitor_closely: {
    bg: 'rgba(255,183,0,0.10)', border: 'rgba(255,183,0,0.3)',
    color: '#7A5B00', label: 'Monitor Closely',
  },
  on_track: {
    bg: 'rgba(134,192,87,0.12)', border: 'rgba(134,192,87,0.3)',
    color: 'var(--color-forest)', label: 'On Track',
  },
}

// ── SVG icons ─────────────────────────────────────────────────────────────

const RefreshIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10" />
    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
  </svg>
)

const TrendEmptyIcon = () => (
  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-text-muted)' }}>
    <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
    <polyline points="16 7 22 7 22 13" />
  </svg>
)

// ── Skeleton loader ───────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--color-border)' }}>
      <div style={{ height: 14, width: '55%', borderRadius: 6, background: 'var(--color-border)', marginBottom: 8 }} />
      <div style={{ height: 12, width: '75%', borderRadius: 6, background: 'var(--color-border)', marginBottom: 8 }} />
      <div style={{ height: 12, width: '30%', borderRadius: 4, background: 'var(--color-border)' }} />
    </div>
  )
}

// ── Trend sparkline chart ─────────────────────────────────────────────────

function TrendChart({ trendData, expectedNextRate }) {
  const chartData = trendData.map(p => ({
    date: new Date(p.session_date).toLocaleDateString([], { month: 'short', day: 'numeric' }),
    rate: Math.round(p.rate * 100),
    projected: false,
  }))

  if (expectedNextRate != null) {
    chartData.push({
      date: 'Next',
      rate: Math.round(expectedNextRate * 100),
      projected: true,
    })
  }

  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="fcastGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="var(--color-primary)" stopOpacity={0.18} />
            <stop offset="95%" stopColor="var(--color-primary)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
          axisLine={false} tickLine={false}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
          unit="%" axisLine={false} tickLine={false}
        />
        <Tooltip
          formatter={(v) => [`${v}%`, 'Attendance']}
          contentStyle={{
            background: '#1A2233', border: 'none', borderRadius: 8,
            color: '#fff', fontSize: 12,
          }}
          labelStyle={{ color: 'var(--color-text-muted)', marginBottom: 4 }}
        />
        <ReferenceLine
          y={70}
          stroke="var(--color-red)"
          strokeDasharray="4 2"
          label={{ value: '70%', fill: 'var(--color-red)', fontSize: 10, position: 'insideTopRight' }}
        />
        <Area
          type="monotone"
          dataKey="rate"
          stroke="var(--color-primary)"
          strokeWidth={2}
          fill="url(#fcastGrad)"
          dot={{ r: 3, fill: 'var(--color-primary)' }}
          activeDot={{ r: 5 }}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

// ── Course list card ──────────────────────────────────────────────────────

function CourseCard({ course, selected, onClick }) {
  const isSelected = selected?.course_id === course.course_id
  const lastRate = course.trend_data?.[course.trend_data.length - 1]?.rate

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
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{
              fontFamily: 'monospace', fontWeight: 700,
              fontSize: 'var(--text-xs)', color: 'var(--color-text-primary)',
            }}>
              {course.course_code}
            </span>
            {course.trend_classification && (
              <span className={CLASSIFICATION_BADGE[course.trend_classification] || 'status-chip-neutral'}>
                {CLASSIFICATION_LABEL[course.trend_classification] || course.trend_classification}
              </span>
            )}
          </div>
          <div style={{
            fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)',
            marginTop: 4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {course.course_name}
          </div>
        </div>
        {lastRate != null && (
          <span className="status-chip-neutral" style={{ flexShrink: 0 }}>
            {pct(lastRate)}
          </span>
        )}
      </div>
      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginTop: 6 }}>
        Updated {formatRelativeTime(course.generated_at)}
      </div>
    </button>
  )
}

// ── Detail panel ──────────────────────────────────────────────────────────

function DetailPanel({ courseId, isAdmin, onRecompute, recomputing, recomputeError }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!courseId) { setDetail(null); return }
    setLoading(true)
    client.get(`/forecasting/${courseId}`)
      .then(r => setDetail(r.data))
      .catch(() => setDetail(null))
      .finally(() => setLoading(false))
  }, [courseId])

  if (!courseId) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', height: '100%',
        color: 'var(--color-text-muted)', gap: 12,
      }}>
        <TrendEmptyIcon />
        <span style={{ fontSize: 'var(--text-sm)' }}>Select a course to view its forecast</span>
      </div>
    )
  }

  if (loading || !detail) {
    return (
      <div style={{ padding: 24 }}>
        {[1, 2, 3].map(i => (
          <div key={i} style={{
            height: 80, borderRadius: 10,
            background: 'var(--color-border)', marginBottom: 14,
          }} />
        ))}
      </div>
    )
  }

  const action = ACTION_CONFIG[detail.suggested_action]

  return (
    <div style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'flex-start', marginBottom: 20,
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <h2 style={{
              fontFamily: "'DM Sans', sans-serif", fontWeight: 700,
              fontSize: 'var(--text-xl)', color: 'var(--color-text-primary)', margin: 0,
            }}>
              {detail.course_code}
            </h2>
            {detail.trend_classification && (
              <span className={CLASSIFICATION_BADGE[detail.trend_classification] || 'status-chip-neutral'}>
                {CLASSIFICATION_LABEL[detail.trend_classification]}
              </span>
            )}
            {detail.confidence_level && (
              <span className="status-chip-neutral" style={{ fontSize: 'var(--text-xs)' }}>
                {detail.confidence_level} confidence
              </span>
            )}
          </div>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)', marginTop: 4 }}>
            {detail.course_name}
          </div>
        </div>
        {isAdmin && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
            <button
              className="btn-secondary"
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              onClick={onRecompute}
              disabled={recomputing}
            >
              <RefreshIcon />
              {recomputing ? 'Starting…' : 'Recompute Now'}
            </button>
            {recomputeError && (
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-red)' }}>
                {recomputeError}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Trend chart or state cards */}
      {!detail.generated_at ? (
        <div className="glass-card" style={{ marginBottom: 20 }}>
          <div style={{
            background: 'rgba(0,117,201,0.06)', border: '1px solid rgba(0,117,201,0.2)',
            borderRadius: 8, padding: '12px 16px',
            fontSize: 'var(--text-sm)', color: 'var(--color-primary)', lineHeight: 1.7,
          }}>
            Generating forecast… this page will refresh automatically.
          </div>
        </div>
      ) : detail.sessions_analyzed === 0 ? (
        <div className="glass-card" style={{ marginBottom: 20 }}>
          <div style={{
            background: 'var(--color-bg)', border: '1px solid var(--color-border)',
            borderRadius: 8, padding: '12px 16px',
            fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)', lineHeight: 1.7,
          }}>
            Not enough session history to generate a forecast. At least 3 completed
            sessions are required.
          </div>
        </div>
      ) : (
        <>
          {/* Trend chart */}
          <div className="glass-card" style={{ marginBottom: 20 }}>
            <div style={{
              fontSize: 'var(--text-xs)', fontWeight: 700, letterSpacing: '0.08em',
              textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 12,
            }}>
              Attendance Trend — Last {detail.sessions_analyzed} Sessions
            </div>
            <TrendChart
              trendData={detail.trend_data}
              expectedNextRate={detail.expected_next_rate}
            />
          </div>

          {/* Stats row */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 12, marginBottom: 20,
          }}>
            {[
              ['Sessions Analyzed', detail.sessions_analyzed],
              ['Projected Next', detail.expected_next_rate != null
                ? pct(detail.expected_next_rate)
                : '—'],
              ['Confidence', detail.confidence_level
                ? detail.confidence_level.charAt(0).toUpperCase() + detail.confidence_level.slice(1)
                : '—'],
            ].map(([label, val]) => (
              <div key={label} style={{
                background: 'var(--color-bg)', borderRadius: 8, padding: '10px 14px',
              }}>
                <div style={{
                  fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginBottom: 4,
                }}>
                  {label}
                </div>
                <div style={{
                  fontSize: 'var(--text-base)', fontWeight: 600,
                  color: 'var(--color-text-primary)',
                }}>
                  {val}
                </div>
              </div>
            ))}
          </div>

          {/* LLM interpretation */}
          <div className="glass-card" style={{ marginBottom: 20 }}>
            <div style={{
              fontSize: 'var(--text-xs)', fontWeight: 700, letterSpacing: '0.08em',
              textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 12,
            }}>
              Trend Analysis
            </div>

            {!detail.ollama_reachable ? (
              <div style={{
                background: 'rgba(255,183,0,0.1)', border: '1px solid rgba(255,183,0,0.3)',
                borderRadius: 8, padding: '12px 16px',
                fontSize: 'var(--text-sm)', color: '#7A5B00', lineHeight: 1.7,
              }}>
                AI interpretation unavailable — the Ollama service was unreachable.
                The trend classification and chart above are still accurate (computed
                from your attendance data directly).
                {isAdmin ? ' Use Recompute Now to retry.' : ' The pipeline will retry automatically.'}
              </div>
            ) : detail.interpretation ? (
              <p style={{
                fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)',
                lineHeight: 1.8, margin: 0,
              }}>
                {detail.interpretation}
              </p>
            ) : (
              <p style={{
                fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)',
                lineHeight: 1.8, margin: 0,
              }}>
                Interpretation not available for this course.
              </p>
            )}
          </div>

          {/* Suggested action banner */}
          {action && (
            <div style={{
              background: action.bg,
              border: `1px solid ${action.border}`,
              borderRadius: 8, padding: '10px 14px',
              fontSize: 'var(--text-sm)', color: action.color,
              fontWeight: 500, marginBottom: 20,
            }}>
              {action.label}
            </div>
          )}
        </>
      )}

      {/* Footer */}
      <div style={{
        fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)',
        borderTop: '1px solid var(--color-border)', paddingTop: 12, marginTop: 4,
      }}>
        {detail.generated_at
          ? `Last updated: ${fmtDate(detail.generated_at)}`
          : 'Forecast generating — this page refreshes automatically'}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function Forecasting() {
  const { professor } = useAuth()
  const isAdmin = professor?.role === 'admin'

  const [courses, setCourses] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [recomputing, setRecomputing] = useState(false)
  const [recomputeError, setRecomputeError] = useState(null)
  const [detailKey, setDetailKey] = useState(0)

  const fetchList = useCallback(() => {
    setLoading(true)
    client.get('/forecasting')
      .then(r => setCourses(r.data))
      .catch(() => setCourses([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { fetchList() }, [fetchList])

  // Auto-poll every 8s while any course is still awaiting its first forecast
  useEffect(() => {
    if (loading) return
    const pending = courses.some(c => !c.generated_at)
    if (!pending) return
    const timer = setTimeout(fetchList, 8000)
    return () => clearTimeout(timer)
  }, [courses, loading, fetchList])

  async function handleRecompute() {
    setRecomputing(true)
    setRecomputeError(null)
    try {
      await client.post('/forecasting/recompute')
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Recompute failed'
      setRecomputeError(msg)
      setRecomputing(false)
      return
    }
    setTimeout(() => {
      fetchList()
      setDetailKey(k => k + 1)
      setRecomputing(false)
    }, 3000)
  }

  return (
    <div style={{ display: 'flex', height: '100%', gap: 20 }}>
      {/* ── Left panel: course list ── */}
      <div
        className="glass-panel"
        style={{ width: 320, display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0 }}
      >
        <div
          className="panel-header"
          style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
        >
          <div>
            <div style={{
              fontFamily: "'DM Sans', sans-serif", fontWeight: 700,
              fontSize: 'var(--text-base)', color: 'var(--color-text-primary)',
            }}>
              Attendance Forecast
            </div>
            {!loading && (
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginTop: 2 }}>
                {courses.length} course{courses.length !== 1 ? 's' : ''}
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
          ) : courses.length === 0 ? (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', height: '100%', gap: 14, padding: 24,
              color: 'var(--color-text-muted)', textAlign: 'center',
            }}>
              <TrendEmptyIcon />
              <span style={{ fontSize: 'var(--text-sm)' }}>No courses available</span>
            </div>
          ) : (
            courses.map(c => (
              <CourseCard
                key={c.course_id}
                course={c}
                selected={selected}
                onClick={() => setSelected(c)}
              />
            ))
          )}
        </div>
      </div>

      {/* ── Right panel: detail ── */}
      <div
        className="glass-panel"
        style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
      >
        <DetailPanel
          key={detailKey}
          courseId={selected?.course_id}
          isAdmin={isAdmin}
          onRecompute={handleRecompute}
          recomputing={recomputing}
          recomputeError={recomputeError}
        />
      </div>
    </div>
  )
}
