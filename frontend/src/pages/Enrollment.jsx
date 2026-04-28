import { useState, useEffect, useRef } from 'react'
import client from '../api/client'

export default function Enrollment() {
  const [students, setStudents]   = useState([])
  const [name, setName]           = useState('')
  const [studentId, setStudentId] = useState('')
  const [created, setCreated]     = useState(null)
  const [captures, setCaptures]   = useState([])
  const [streaming, setStreaming] = useState(false)
  const [enrollMsg, setEnrollMsg] = useState('')
  const [loading, setLoading]     = useState(false)

  const videoRef = useRef(null)
  const streamRef = useRef(null)

  useEffect(() => {
    client.get('/students').then(r => setStudents(r.data)).catch(() => {})
    return () => stopCamera()
  }, [])

  async function createStudent(e) {
    e.preventDefault()
    setLoading(true)
    try {
      const r = await client.post('/students', { name, student_id: studentId })
      setCreated(r.data)
      setStudents(prev => [r.data, ...prev])
      setName('')
      setStudentId('')
      setCaptures([])
      setEnrollMsg('')
    } catch (err) {
      alert(err.response?.data?.detail ?? 'Failed to create student')
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
      alert('Camera access denied: ' + err.message)
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
      setEnrollMsg(`Enrolled successfully (${r.data.frames_captured} frames)`)
      setCaptures([])
      stopCamera()
    } catch (err) {
      setEnrollMsg('Enrollment failed: ' + (err.response?.data?.detail ?? err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-xl font-bold text-white">Enrollment</h1>

      <div className="grid grid-cols-12 gap-5">
        {/* Student list */}
        <div className="col-span-4 bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-800">
            <h2 className="text-sm font-semibold text-white">Students ({students.length})</h2>
          </div>
          <div className="overflow-y-auto max-h-[60vh]">
            {students.length === 0 ? (
              <p className="text-center text-gray-600 text-sm py-8">No students yet</p>
            ) : (
              <ul className="divide-y divide-gray-800">
                {students.map(s => (
                  <li key={s.id}
                    onClick={() => { setCreated(s); setCaptures([]); setEnrollMsg('') }}
                    className={`px-4 py-3 cursor-pointer hover:bg-gray-800/50 transition-colors ${
                      created?.id === s.id ? 'bg-indigo-900/30 border-l-2 border-indigo-500' : ''
                    }`}
                  >
                    <p className="text-sm text-white font-medium">{s.name}</p>
                    <p className="text-xs text-gray-500 font-mono mt-0.5">{s.student_id}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Right panel */}
        <div className="col-span-8 space-y-4">
          {/* Create student form */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
            <h2 className="text-sm font-semibold text-white mb-4">Create Student</h2>
            <form onSubmit={createStudent} className="flex gap-3">
              <input
                placeholder="Full Name"
                value={name}
                onChange={e => setName(e.target.value)}
                required
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              />
              <input
                placeholder="Student ID"
                value={studentId}
                onChange={e => setStudentId(e.target.value)}
                required
                className="w-36 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
              />
              <button type="submit" disabled={loading}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg font-medium disabled:opacity-50">
                Create
              </button>
            </form>
          </div>

          {/* Face enrollment */}
          {created && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-white">
                  Enroll Face — <span className="text-indigo-400">{created.name}</span>
                </h2>
                <span className="text-xs text-gray-500">{captures.length}/5 frames</span>
              </div>

              {/* Camera preview */}
              <div className="relative bg-black rounded-xl overflow-hidden aspect-video max-w-md">
                <video
                  ref={videoRef}
                  autoPlay
                  muted
                  playsInline
                  className={`w-full h-full object-cover ${streaming ? '' : 'hidden'}`}
                />
                {!streaming && (
                  <div className="flex items-center justify-center h-full text-gray-600 text-sm">
                    Camera off
                  </div>
                )}
              </div>

              {/* Camera controls */}
              <div className="flex gap-3">
                {!streaming ? (
                  <button onClick={startCamera}
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg">
                    Start Camera
                  </button>
                ) : (
                  <>
                    <button
                      onClick={captureFrame}
                      disabled={captures.length >= 5}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg disabled:opacity-50"
                    >
                      Capture
                    </button>
                    <button onClick={stopCamera}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg">
                      Stop
                    </button>
                  </>
                )}
                {captures.length > 0 && (
                  <button
                    onClick={enrollFace}
                    disabled={loading}
                    className="px-4 py-2 bg-green-700 hover:bg-green-600 text-white text-sm rounded-lg font-medium disabled:opacity-50 ml-auto"
                  >
                    {loading ? 'Enrolling…' : `Enroll Face (${captures.length})`}
                  </button>
                )}
              </div>

              {/* Capture thumbnails */}
              {captures.length > 0 && (
                <div className="flex gap-2 flex-wrap">
                  {captures.map((c, i) => (
                    <div key={i} className="relative">
                      <img src={c.url} alt={`frame ${i + 1}`}
                        className="w-20 h-14 object-cover rounded-lg border border-gray-700" />
                      <button
                        onClick={() => setCaptures(prev => prev.filter((_, j) => j !== i))}
                        className="absolute -top-1 -right-1 w-5 h-5 bg-red-600 text-white text-xs rounded-full flex items-center justify-center"
                      >×</button>
                    </div>
                  ))}
                </div>
              )}

              {enrollMsg && (
                <p className={`text-sm ${enrollMsg.startsWith('Enrolled') ? 'text-green-400' : 'text-red-400'}`}>
                  {enrollMsg}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
