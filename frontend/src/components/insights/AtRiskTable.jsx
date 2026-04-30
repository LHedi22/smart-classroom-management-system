import { useState, useEffect } from 'react'
import client from '../../api/client'

const ChevronIcon = ({ expanded }) => (
  <svg
    width="12" height="12" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
    style={{ transition: 'transform 0.18s ease', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)', flexShrink: 0 }}
  >
    <polyline points="9 18 15 12 9 6"/>
  </svg>
)

function riskLevel(student) {
  if (student.attendance_rate < 0.50 || student.consecutive_absences >= 5) return 'high'
  return 'medium'
}

function RiskBadge({ level }) {
  const styles = {
    high:   { bg: 'rgba(236,0,68,0.08)',    color: 'var(--color-red)',    border: 'rgba(236,0,68,0.22)' },
    medium: { bg: 'rgba(255,183,0,0.12)',   color: '#7A5B00',             border: 'rgba(255,183,0,0.32)' },
  }
  const s = styles[level] ?? styles.medium
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      borderRadius: 999, padding: '3px 10px', fontSize: 11, fontWeight: 600,
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
      letterSpacing: '0.03em', textTransform: 'capitalize',
    }}>
      {level === 'high' ? '● ' : '○ '}{level}
    </span>
  )
}

function AttendanceBar({ rate }) {
  const pct = Math.round(rate * 100)
  const color = pct >= 70 ? 'var(--color-green)' : pct >= 50 ? 'var(--color-yellow)' : 'var(--color-red)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 99, background: 'var(--color-border)', overflow: 'hidden', minWidth: 60 }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 99, transition: 'width 0.3s ease' }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-text-secondary)', width: 34, textAlign: 'right', flexShrink: 0 }}>{pct}%</span>
    </div>
  )
}

function ProfileRow({ studentId }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client.get(`/insights/students/${studentId}/profile`)
      .then(r => setProfile(r.data))
      .catch(() => setProfile(null))
      .finally(() => setLoading(false))
  }, [studentId])

  if (loading) return (
    <div style={{ padding: '12px 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
      {[1, 2].map(i => <div key={i} className="skeleton" style={{ height: 20, borderRadius: 6, opacity: 0.8 - i * 0.2 }} />)}
    </div>
  )

  if (!profile) return (
    <div style={{ padding: '12px 20px', color: 'var(--color-text-muted)', fontSize: 13 }}>Could not load profile.</div>
  )

  return (
    <div style={{ padding: '14px 20px 16px 44px', background: 'rgba(0,117,201,0.02)', borderTop: '1px solid var(--color-border)' }}>
      <p style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)', marginBottom: 10 }}>Course Breakdown</p>
      {profile.per_course?.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {profile.per_course.map(c => (
            <div key={c.course_code} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-text-secondary)', width: 72, flexShrink: 0, fontFamily: 'monospace' }}>{c.course_code}</span>
              <AttendanceBar rate={c.rate} />
              <span style={{ fontSize: 12, color: 'var(--color-text-muted)', flexShrink: 0 }}>{c.sessions_attended}/{c.sessions_total} sessions</span>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>No course data available.</p>
      )}
    </div>
  )
}

export default function AtRiskTable({ students = [] }) {
  const [expandedId, setExpandedId] = useState(null)
  const [sortKey, setSortKey] = useState('attendance_rate')
  const [sortAsc, setSortAsc] = useState(true)

  function toggleSort(key) {
    if (sortKey === key) setSortAsc(a => !a)
    else { setSortKey(key); setSortAsc(true) }
  }

  const sorted = [...students].sort((a, b) => {
    const av = a[sortKey]; const bv = b[sortKey]
    if (av == null) return 1; if (bv == null) return -1
    return sortAsc ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
  })

  const thStyle = (key) => ({
    textAlign: 'left', padding: '11px 14px', cursor: 'pointer',
    userSelect: 'none',
    color: sortKey === key ? 'var(--color-primary)' : undefined,
  })

  const sortIndicator = (key) => sortKey === key ? (sortAsc ? ' ↑' : ' ↓') : ''

  if (students.length === 0) return (
    <div style={{ textAlign: 'center', padding: '40px 24px', color: 'var(--color-text-muted)' }}>
      <div style={{
        width: 56, height: 56, borderRadius: '50%', background: 'rgba(134,192,87,0.1)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px',
      }}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-forest)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
      </div>
      <p style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 4 }}>All students are on track</p>
      <p style={{ fontSize: 13 }}>No students are flagged as at-risk.</p>
    </div>
  )

  return (
    <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
      <thead>
        <tr className="table-head-row">
          <th style={{ width: 24, padding: '11px 8px 11px 14px' }} />
          <th style={thStyle('name')} onClick={() => toggleSort('name')}>Name{sortIndicator('name')}</th>
          <th style={thStyle('institutional_id')} onClick={() => toggleSort('institutional_id')}>ID</th>
          <th style={thStyle('attendance_rate')} onClick={() => toggleSort('attendance_rate')}>Attendance{sortIndicator('attendance_rate')}</th>
          <th style={thStyle('consecutive_absences')} onClick={() => toggleSort('consecutive_absences')}>Consec. Absent{sortIndicator('consecutive_absences')}</th>
          <th style={{ textAlign: 'left', padding: '11px 14px' }}>Courses At Risk</th>
          <th style={{ textAlign: 'left', padding: '11px 14px' }}>Risk Level</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map(student => {
          const level = riskLevel(student)
          const isExpanded = expandedId === student.student_id

          return (
            <>
              <tr
                key={student.student_id}
                className="table-row"
                onClick={() => setExpandedId(isExpanded ? null : student.student_id)}
                style={{ cursor: 'pointer', background: isExpanded ? 'rgba(0,117,201,0.025)' : undefined }}
              >
                <td style={{ padding: '12px 8px 12px 14px', color: 'var(--color-text-muted)' }}>
                  <ChevronIcon expanded={isExpanded} />
                </td>
                <td style={{ padding: '12px 14px', fontWeight: 600, color: 'var(--color-text-primary)' }}>{student.name}</td>
                <td style={{ padding: '12px 14px', color: 'var(--color-text-muted)', fontFamily: 'monospace', fontSize: 12 }}>{student.institutional_id || '—'}</td>
                <td style={{ padding: '12px 14px', minWidth: 140 }}>
                  <AttendanceBar rate={student.attendance_rate} />
                </td>
                <td style={{ padding: '12px 14px', fontWeight: student.consecutive_absences >= 3 ? 700 : 400, color: student.consecutive_absences >= 3 ? 'var(--color-red)' : 'var(--color-text-primary)' }}>
                  {student.consecutive_absences}
                </td>
                <td style={{ padding: '12px 14px' }}>
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {(student.courses_at_risk ?? []).map(c => (
                      <span key={c} className="status-chip-neutral" style={{ fontFamily: 'monospace', fontSize: 11 }}>{c}</span>
                    ))}
                  </div>
                </td>
                <td style={{ padding: '12px 14px' }}>
                  <RiskBadge level={level} />
                </td>
              </tr>
              {isExpanded && (
                <tr key={student.student_id + '-profile'}>
                  <td colSpan={7} style={{ padding: 0 }}>
                    <ProfileRow studentId={student.student_id} />
                  </td>
                </tr>
              )}
            </>
          )
        })}
      </tbody>
    </table>
  )
}
