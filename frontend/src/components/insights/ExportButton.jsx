import { useState } from 'react'

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

function DownloadIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0 }}>
      <path d="M8 1v9M4.5 6.5 8 10l3.5-3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M2 13h12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
    </svg>
  )
}

/**
 * Props:
 *   type: 'session-pdf' | 'course-pdf' | 'course-csv'
 *   id: string  (session_id or course_id)
 *   label: string (optional button label)
 *   variant: 'primary' | 'secondary' (default 'secondary')
 */
export default function ExportButton({ type, id, label, variant = 'secondary' }) {
  const [loading, setLoading] = useState(false)

  async function handleClick() {
    if (loading || !id) return
    setLoading(true)
    try {
      let url, filename, mime
      if (type === 'session-pdf') {
        url = `${BASE}/insights/export/session/${id}`
        filename = `session_${id}.pdf`
        mime = 'application/pdf'
      } else if (type === 'course-pdf') {
        url = `${BASE}/insights/export/course/${id}`
        filename = `course_${id}.pdf`
        mime = 'application/pdf'
      } else {
        url = `${BASE}/insights/export/course/${id}/csv`
        filename = `course_${id}.csv`
        mime = 'text/csv'
      }

      const token = localStorage.getItem('sc_token')
      const headers = token ? { Authorization: `Bearer ${token}` } : {}
      const res = await fetch(url, { headers })
      if (!res.ok) throw new Error(`Export failed: ${res.status}`)

      const blob = await res.blob()
      const objUrl = URL.createObjectURL(new Blob([blob], { type: mime }))
      const a = document.createElement('a')
      a.href = objUrl
      a.download = filename
      a.click()
      URL.revokeObjectURL(objUrl)
    } catch (err) {
      console.error('Export error:', err)
    } finally {
      setLoading(false)
    }
  }

  const btnClass = variant === 'primary' ? 'btn-primary' : 'btn-secondary'
  const text = label ?? (type === 'course-csv' ? 'Export CSV' : 'Export PDF')

  return (
    <button
      onClick={handleClick}
      disabled={loading || !id}
      className={btnClass}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13 }}
    >
      <DownloadIcon />
      {loading ? 'Exporting…' : text}
    </button>
  )
}
