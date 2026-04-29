import { useState, useEffect, useRef } from 'react'
import client from '../api/client'

// ── Camera icon ───────────────────────────────────────────────────────────

const CameraIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
    <circle cx="12" cy="13" r="4"/>
  </svg>
)

const UserIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
    <circle cx="12" cy="7" r="4"/>
  </svg>
)

// ── Student list item ─────────────────────────────────────────────────────

function StudentListItem({ student, selected, onClick }) {
  const initial = student.name.charAt(0).toUpperCase()
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%',
        textAlign: 'left',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '11px 14px',
        border: 'none',
        borderBottom: '1px solid var(--color-border)',
        background: selected ? 'rgba(87,47,135,0.06)' : 'transparent',
        cursor: 'pointer',
        transition: 'background 0.12s ease',
        outline: 'none',
        borderLeft: selected ? '3px solid var(--color-purple)' : '3px solid transparent',
      }}
    >
      <div style={{
        width: 34, height: 34, borderRadius: '50%',
        background: selected ? 'rgba(87,47,135,0.15)' : 'rgba(87,47,135,0.09)',
        color: 'var(--color-purple)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: "'DM Sans', sans-serif",
        fontWeight: 700, fontSize: 14,
        flexShrink: 0,
        transition: 'background 0.12s ease',
      }}>
        {initial}
      </div>
      <div style={{ minWidth: 0 }}>
        <p style={{ fontWeight: 600, fontSize: 13, color: 'var(--color-text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {student.name}
        </p>
        <p style={{ fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'monospace', marginTop: 1 }}>
          {student.student_id}
        </p>
      </div>
    </button>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function Enrollment() {
  const [students,   setStudents]   = useState([])
  const [name,       setName]       = useState('')
  const [studentId,  setStudentId]  = useState('')
  const [created,    setCreated]    = useState(null)
  const [captures,   setCaptures]   = useState([])
  const [streaming,  setStreaming]  = useState(false)
  const [enrollMsg,  setEnrollMsg]  = useState('')
  const [enrollOk,   setEnrollOk]   = useState(false)
  const [loading,    setLoading]    = useState(false)
  const [formError,  setFormError]  = useState('')

  const videoRef  = useRef(null)
  const streamRef = useRef(null)

  useEffect(() => {
    client.get('/students').then(r => setStudents(r.data)).catch(() => {})
    return () => stopCamera()
  }, [])

  async function createStudent(e) {
    e.preventDefault()
    setFormError('')
    setLoading(true)
    try {
      const r = await client.post('/students', { name, student_id: studentId })
      setCreated(r.data)
      setStudents(prev => [r.data, ...prev])
      setName('')
      setStudentId('')
      setCaptures([])
      setEnrollMsg('')
      setEnrollOk(false)
    } catch (err) {
      setFormError(err.response?.data?.detail ?? 'Failed to create student')
    } finally {
      setLoading(false)
    }
  }

  async function startCamera() {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: true })
      streamRef.current = s
      if (videoRef.current) videoRef.current.srcObject = s
      setStreaming(true)
    } catch (err) {
      setEnrollMsg('Camera access denied: ' + err.message)
      setEnrollOk(false)
    }
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
    setStreaming(false)
  }

  function captureFrame() {
    const video = videoRef.current
    if (!video) return
    const canvas = document.createElement('canvas')
    canvas.width  = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)
    canvas.toBlob(blob => {
      if (!blob) return
      const url = URL.createObjectURL(blob)
      setCaptures(prev => [...prev, { blob, url }])
    }, 'image/jpeg', 0.92)
  }

  async function enrollFace() {
    if (!created || captures.length === 0) return
    setLoading(true)
    setEnrollMsg('')
    try {
      const fd = new FormData()
      captures.forEach((c, i) => fd.append('files', c.blob, `frame_${i}.jpg`))
      const r = await client.post(`/students/${created.id}/enroll-face`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setEnrollMsg(`Face enrolled — ${r.data.frames_captured} frames captured.`)
      setEnrollOk(true)
      setCaptures([])
      stopCamera()
    } catch (err) {
      setEnrollMsg('Enrollment failed: ' + (err.response?.data?.detail ?? err.message))
      setEnrollOk(false)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-shell">
      {/* Page header */}
      <section className="page-header-card">
        <div className="page-header-row">
          <h1 className="section-title">Enrollment</h1>
          <span className="status-chip-neutral">{students.length} students</span>
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 20, flex: 1, minHeight: 0 }}>

        {/* ── Student list ────────────────────────────────────────── */}
        <div className="table-shell" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="panel-header">
            <h2 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 700, color: 'var(--color-text-primary)' }}>
              Students ({students.length})
            </h2>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {students.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">
                  <UserIcon />
                </div>
                <p className="empty-state-title">No students yet</p>
                <p className="empty-state-desc">Create a student using the form to get started.</p>
              </div>
            ) : (
              students.map(s => (
                <StudentListItem
                  key={s.id}
                  student={s}
                  selected={created?.id === s.id}
                  onClick={() => { setCreated(s); setCaptures([]); setEnrollMsg(''); setEnrollOk(false) }}
                />
              ))
            )}
          </div>
        </div>

        {/* ── Right panel ─────────────────────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Create student form */}
          <div className="glass-card">
            <h2 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 15, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 16 }}>
              Add student
            </h2>
            <form onSubmit={createStudent} style={{ display: 'flex', gap: 10 }}>
              <input
                placeholder="Full name"
                value={name}
                onChange={e => setName(e.target.value)}
                required
                className="field-control"
                style={{ flex: 1 }}
              />
              <input
                placeholder="Student ID"
                value={studentId}
                onChange={e => setStudentId(e.target.value)}
                required
                className="field-control"
                style={{ width: 140 }}
              />
              <button type="submit" disabled={loading} className="btn-primary" style={{ flexShrink: 0 }}>
                {loading ? 'Creating…' : 'Create'}
              </button>
            </form>
            {formError && (
              <p style={{ marginTop: 10, fontSize: 13, color: 'var(--color-red)', background: 'rgba(236,0,68,0.06)', border: '1px solid rgba(236,0,68,0.18)', borderRadius: 8, padding: '8px 12px' }}>
                {formError}
              </p>
            )}
          </div>

          {/* Face enrollment */}
          {created ? (
            <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <h2 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 15, fontWeight: 700, color: 'var(--color-text-primary)' }}>
                  Face enrollment —{' '}
                  <span style={{ color: 'var(--color-purple)' }}>{created.name}</span>
                </h2>
                <span className="status-chip-neutral" style={{ fontSize: 11 }}>{captures.length}/5 frames</span>
              </div>

              {/* Camera preview */}
              <div style={{
                position: 'relative', borderRadius: 12, overflow: 'hidden',
                aspectRatio: '16/9', maxWidth: 440,
                border: '1px solid var(--color-border)',
                background: 'rgba(26,34,51,0.96)',
              }}>
                <video
                  ref={videoRef}
                  autoPlay muted playsInline
                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: streaming ? 'block' : 'none' }}
                />
                {!streaming && (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 8 }}>
                    <div style={{ color: 'rgba(255,255,255,0.3)' }}>
                      <CameraIcon />
                    </div>
                    <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.35)' }}>Camera off</p>
                  </div>
                )}
              </div>

              {/* Camera controls */}
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                {!streaming ? (
                  <button onClick={startCamera} className="btn-secondary">Start camera</button>
                ) : (
                  <>
                    <button
                      onClick={captureFrame}
                      disabled={captures.length >= 5}
                      className="btn-primary"
                    >
                      Capture frame
                    </button>
                    <button onClick={stopCamera} className="btn-secondary">Stop</button>
                  </>
                )}
                {captures.length > 0 && (
                  <button
                    onClick={enrollFace}
                    disabled={loading}
                    className="btn-success"
                    style={{ marginLeft: 'auto' }}
                  >
                    {loading ? 'Enrolling…' : `Enroll face (${captures.length})`}
                  </button>
                )}
              </div>

              {/* Capture thumbnails */}
              {captures.length > 0 && (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {captures.map((c, i) => (
                    <div key={i} style={{ position: 'relative' }}>
                      <img
                        src={c.url}
                        alt={`Frame ${i + 1}`}
                        style={{ width: 72, height: 52, objectFit: 'cover', borderRadius: 8, border: '1px solid var(--color-border)', display: 'block' }}
                      />
                      <button
                        onClick={() => setCaptures(prev => prev.filter((_, j) => j !== i))}
                        style={{
                          position: 'absolute', top: -6, right: -6,
                          width: 20, height: 20, borderRadius: '50%',
                          background: 'var(--color-red)', color: 'white',
                          border: 'none', cursor: 'pointer',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 13, fontWeight: 700, lineHeight: 1,
                          boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                        }}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Result message */}
              {enrollMsg && (
                <p style={{
                  fontSize: 13, fontWeight: 600,
                  color: enrollOk ? 'var(--color-forest)' : 'var(--color-red)',
                  background: enrollOk ? 'rgba(134,192,87,0.1)' : 'rgba(236,0,68,0.07)',
                  border: `1px solid ${enrollOk ? 'rgba(134,192,87,0.3)' : 'rgba(236,0,68,0.2)'}`,
                  borderRadius: 8, padding: '10px 14px',
                }}>
                  {enrollMsg}
                </p>
              )}
            </div>
          ) : (
            <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 200, gap: 12, textAlign: 'center' }}>
              <div style={{ width: 48, height: 48, borderRadius: 14, background: 'rgba(87,47,135,0.09)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-purple)' }}>
                <CameraIcon />
              </div>
              <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-secondary)' }}>Select a student</p>
              <p style={{ fontSize: 13, color: 'var(--color-text-muted)', maxWidth: 280, lineHeight: 1.5 }}>
                Choose a student from the list to enroll their face for recognition.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
