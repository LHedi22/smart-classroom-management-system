import { useState, useEffect } from 'react'
import client from '../api/client'

const FALLBACK_DATA = {
  overview: {
    total_sessions: 12,
    avg_attendance_rate: 0.74,
    active_alerts_count: 2,
    comfort_score: 72,
    at_risk_count: 3,
  },
  atRiskStudents: [
    { student_id: 'demo-1', name: 'Alice Demo',  institutional_id: 'STU001', attendance_rate: 0.45, consecutive_absences: 4, courses_at_risk: ['CS301'] },
    { student_id: 'demo-2', name: 'Bob Demo',    institutional_id: 'STU002', attendance_rate: 0.62, consecutive_absences: 2, courses_at_risk: ['MATH201'] },
    { student_id: 'demo-3', name: 'Carol Demo',  institutional_id: 'STU003', attendance_rate: 0.38, consecutive_absences: 6, courses_at_risk: ['CS301', 'PHY101'] },
  ],
  attendanceTrend: [
    { week_label: 'W1', attendance_rate: 0.88 },
    { week_label: 'W2', attendance_rate: 0.82 },
    { week_label: 'W3', attendance_rate: 0.79 },
    { week_label: 'W4', attendance_rate: 0.85 },
    { week_label: 'W5', attendance_rate: 0.73 },
    { week_label: 'W6', attendance_rate: 0.68 },
    { week_label: 'W7', attendance_rate: 0.71 },
    { week_label: 'W8', attendance_rate: 0.74 },
  ],
  heatmap: [
    { day_of_week: 0, hour_slot: 0, avg_rate: 0.82 },
    { day_of_week: 0, hour_slot: 1, avg_rate: 0.78 },
    { day_of_week: 1, hour_slot: 0, avg_rate: 0.91 },
    { day_of_week: 1, hour_slot: 1, avg_rate: 0.88 },
    { day_of_week: 2, hour_slot: 0, avg_rate: 0.75 },
    { day_of_week: 2, hour_slot: 2, avg_rate: 0.60 },
    { day_of_week: 3, hour_slot: 1, avg_rate: 0.85 },
    { day_of_week: 4, hour_slot: 0, avg_rate: 0.70 },
    { day_of_week: 4, hour_slot: 1, avg_rate: 0.65 },
  ],
  envTrends: Array.from({ length: 7 }, (_, i) => ({
    date: new Date(Date.now() - (6 - i) * 86400000).toISOString().slice(0, 10),
    temp_avg: +(22 + Math.sin(i) * 4 + 2).toFixed(1),
    temp_min: +(20 + Math.sin(i) * 3).toFixed(1),
    temp_max: +(26 + Math.sin(i) * 4).toFixed(1),
    humidity_avg: +(55 + Math.cos(i) * 10).toFixed(1),
    air_quality_avg: +(320 + Math.sin(i * 1.3) * 80).toFixed(0),
  })),
  correlations: Array.from({ length: 15 }, (_, i) => ({
    session_id: `demo-${i}`,
    course_code: ['CS301', 'MATH201', 'PHY101'][i % 3],
    date: new Date(Date.now() - i * 3 * 86400000).toISOString().slice(0, 10),
    avg_temp: +(20 + Math.random() * 14).toFixed(1),
    attendance_rate: +(0.5 + Math.random() * 0.45).toFixed(2),
  })),
}

export default function useInsights({ courseId } = {}) {
  const [overview, setOverview]               = useState(null)
  const [atRiskStudents, setAtRiskStudents]   = useState([])
  const [attendanceTrend, setAttendanceTrend] = useState([])
  const [heatmap, setHeatmap]                 = useState([])
  const [envTrends, setEnvTrends]             = useState([])
  const [correlations, setCorrelations]       = useState([])
  const [loading, setLoading]                 = useState(true)
  const [error, setError]                     = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)

    const courseParams = courseId ? { course_id: courseId } : {}

    Promise.all([
      client.get('/insights/overview'),
      client.get('/insights/students/at-risk', { params: courseParams }),
      client.get('/insights/attendance/trend', { params: { ...courseParams, weeks: 8 } }),
      client.get('/insights/attendance/heatmap'),
      client.get('/insights/environment/trends', { params: { room_id: 'room1' } }),
      client.get('/insights/correlations/temp-vs-attendance'),
    ])
      .then(([ovRes, riskRes, trendRes, hmRes, envRes, corrRes]) => {
        setOverview(ovRes.data)
        setAtRiskStudents(riskRes.data)
        setAttendanceTrend(trendRes.data)
        setHeatmap(hmRes.data)
        setEnvTrends(envRes.data)
        setCorrelations(corrRes.data)
      })
      .catch(() => {
        setError('Backend unreachable — showing demo data')
        setOverview(FALLBACK_DATA.overview)
        setAtRiskStudents(FALLBACK_DATA.atRiskStudents)
        setAttendanceTrend(FALLBACK_DATA.attendanceTrend)
        setHeatmap(FALLBACK_DATA.heatmap)
        setEnvTrends(FALLBACK_DATA.envTrends)
        setCorrelations(FALLBACK_DATA.correlations)
      })
      .finally(() => setLoading(false))
  }, [courseId])

  return { overview, atRiskStudents, attendanceTrend, heatmap, envTrends, correlations, loading, error }
}
