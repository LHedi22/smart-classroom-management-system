import { useState, useEffect } from 'react'
import useInsights from '../hooks/useInsights'
import KpiCards from '../components/insights/KpiCards'
import AttendanceTrendChart from '../components/insights/AttendanceTrendChart'
import DayOfWeekHeatmap from '../components/insights/DayOfWeekHeatmap'
import AtRiskTable from '../components/insights/AtRiskTable'
import ComfortScoreCard from '../components/insights/ComfortScoreCard'
import SensorTrendChart from '../components/insights/SensorTrendChart'
import CorrelationScatter from '../components/insights/CorrelationScatter'
import AiSummaryCard from '../components/insights/AiSummaryCard'
import ExportButton from '../components/insights/ExportButton'
import client from '../api/client'

const TABS = ['Overview', 'Students', 'Environment']

function TabBar({ active, onChange }) {
  return (
    <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)', marginBottom: 24, gap: 0 }}>
      {TABS.map(t => (
        <button
          key={t}
          onClick={() => onChange(t)}
          className={active === t ? 'tab-btn-active' : 'tab-btn-inactive'}
          style={{ textTransform: 'none', fontSize: 14 }}
        >
          {t}
        </button>
      ))}
    </div>
  )
}

function DemoBanner() {
  return (
    <div style={{
      background: 'rgba(255,183,0,0.10)',
      border: '1px solid rgba(255,183,0,0.32)',
      borderRadius: 8,
      padding: '10px 16px',
      fontSize: 12,
      color: '#7A5B00',
      fontWeight: 500,
      marginBottom: 20,
    }}>
      Demo mode — backend unreachable. Showing sample data.
    </div>
  )
}

// ── Overview tab ──────────────────────────────────────────────────────────

function OverviewTab({ overview, attendanceTrend, heatmap, loading }) {
  if (loading) return <LoadingGrid />
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <KpiCards overview={overview} attendanceTrend={attendanceTrend} />
      <AiSummaryCard scope="global" id="all" title="Global AI Summary" />
      <AttendanceTrendChart data={attendanceTrend} height={220} />
      <DayOfWeekHeatmap data={heatmap} />
    </div>
  )
}

// ── Students tab ──────────────────────────────────────────────────────────

function StudentsTab({ atRiskStudents, loading }) {
  const [courses,          setCourses]          = useState([])
  const [courseId,         setCourseId]         = useState('')
  const [filteredStudents, setFilteredStudents] = useState(null)
  const [filterLoading,    setFilterLoading]    = useState(false)

  useEffect(() => {
    client.get('/courses').then(r => setCourses(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    if (!courseId) { setFilteredStudents(null); return }
    setFilterLoading(true)
    client.get('/insights/students/at-risk', { params: { course_id: courseId } })
      .then(r => setFilteredStudents(r.data))
      .catch(() => setFilteredStudents([]))
      .finally(() => setFilterLoading(false))
  }, [courseId])

  const displayStudents = (courseId && filteredStudents != null) ? filteredStudents : atRiskStudents

  if (loading) return <LoadingGrid />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Course filter */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-secondary)' }}>Filter by course:</label>
        <select
          value={courseId}
          onChange={e => setCourseId(e.target.value)}
          className="field-control"
          style={{ width: 220 }}
        >
          <option value="">All courses</option>
          {courses.map(c => (
            <option key={c.id} value={c.id}>{c.code} — {c.name}</option>
          ))}
        </select>
        {courseId && (
          <>
            <button onClick={() => setCourseId('')} className="btn-secondary" style={{ padding: '7px 12px', fontSize: 12 }}>
              Clear
            </button>
            <ExportButton type="course-pdf" id={courseId} />
            <ExportButton type="course-csv" id={courseId} />
          </>
        )}
      </div>

      {courseId && (
        <AiSummaryCard scope="course" id={courseId} title="Course AI Summary" />
      )}

      <div className="table-shell">
        {filterLoading ? (
          <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height: 44, borderRadius: 8 }} />)}
          </div>
        ) : (
          <AtRiskTable students={displayStudents} />
        )}
      </div>
    </div>
  )
}

// ── Environment tab ───────────────────────────────────────────────────────

function EnvironmentTab({ overview, envTrends, correlations, loading }) {
  if (loading) return <LoadingGrid />
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 16, alignItems: 'start' }}>
        <ComfortScoreCard score={overview?.comfort_score ?? 0} />
        <SensorTrendChart data={envTrends} height={240} />
      </div>
      <CorrelationScatter data={correlations} />
      <AiSummaryCard scope="room" id="room1" title="Room Analysis" />
    </div>
  )
}

// ── Loading skeleton ──────────────────────────────────────────────────────

function LoadingGrid() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
        {[1,2,3,4].map(i => <div key={i} className="skeleton" style={{ height: 100, borderRadius: 12 }} />)}
      </div>
      <div className="skeleton" style={{ height: 240, borderRadius: 12 }} />
      <div className="skeleton" style={{ height: 200, borderRadius: 12 }} />
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function Insights() {
  const [activeTab, setActiveTab] = useState('Overview')
  const { overview, atRiskStudents, attendanceTrend, heatmap, envTrends, correlations, loading, error } = useInsights()

  return (
    <div className="page-shell">
      <section className="page-header-card">
        <div className="page-header-row">
          <div>
            <h1 className="section-title">Insights</h1>
            <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginTop: 2 }}>
              Analytics, at-risk detection, and environmental correlations
            </p>
          </div>
        </div>
      </section>

      <section style={{ flex: 1 }}>
        {error && <DemoBanner />}
        <TabBar active={activeTab} onChange={setActiveTab} />

        {activeTab === 'Overview' && (
          <OverviewTab overview={overview} attendanceTrend={attendanceTrend} heatmap={heatmap} loading={loading} />
        )}
        {activeTab === 'Students' && (
          <StudentsTab atRiskStudents={atRiskStudents} loading={loading} />
        )}
        {activeTab === 'Environment' && (
          <EnvironmentTab overview={overview} envTrends={envTrends} correlations={correlations} loading={loading} />
        )}
      </section>
    </div>
  )
}
