import { useState, useEffect, useRef, useCallback } from 'react'

const WS_PATH = '/ws/classroom/room1'
const INITIAL_BACKOFF = 3_000
const MAX_BACKOFF = 30_000
const DEMO_TIMEOUT_MS = 8_000

function makeMockSensors() {
  const t = Date.now() / 1000
  return {
    temperature: { value: +(22 + 5 * Math.abs(Math.sin(t / 60)) + (Math.random() - 0.5) * 0.6).toFixed(1), unit: 'C' },
    humidity:    { value: +(50 + 10 * Math.abs(Math.sin(t / 90)) + (Math.random() - 0.5) * 2).toFixed(1), unit: '%' },
    air_quality: { value: +(250 + 150 * Math.abs(Math.sin(t / 120)) + (Math.random() - 0.5) * 20).toFixed(0), unit: 'ppm' },
    sound:       { value: Math.random() < 0.7 ? 1 : 0, unit: 'bool' },
  }
}

export default function useLiveSensors() {
  const [sensors, setSensors]         = useState({})
  const [attendance, setAttendance]   = useState([])
  const [alerts, setAlerts]           = useState([])
  const [relayStatus, setRelayStatus] = useState({ ac: 'auto', lighting: 'auto' })
  const [isConnected, setIsConnected] = useState(false)
  const [isDemoMode, setIsDemoMode]   = useState(false)

  const wsRef           = useRef(null)
  const backoff         = useRef(INITIAL_BACKOFF)
  const retryTimer      = useRef(null)
  const dead            = useRef(false)
  const lastMessageTime = useRef(null)
  const demoInterval    = useRef(null)
  const inDemoMode      = useRef(false)   // sync ref — avoids stale closures in callbacks

  const stopDemo = useCallback(() => {
    if (demoInterval.current) {
      clearInterval(demoInterval.current)
      demoInterval.current = null
    }
    inDemoMode.current = false
    setIsDemoMode(false)
  }, [])

  const startDemo = useCallback(() => {
    if (inDemoMode.current) return
    inDemoMode.current = true
    setIsDemoMode(true)
    setSensors(makeMockSensors())
    demoInterval.current = setInterval(() => setSensors(makeMockSensors()), 5_000)
  }, [])

  const handleMessage = useCallback((msg) => {
    lastMessageTime.current = Date.now()
    // Real data arrived — exit demo mode if active
    if (inDemoMode.current) stopDemo()

    switch (msg.type) {
      case 'snapshot':
        setSensors(msg.sensors ?? {})
        setRelayStatus(msg.relay ?? { ac: 'auto', lighting: 'auto' })
        break
      case 'sensor':
        setSensors(prev => ({
          ...prev,
          [msg.sensor_type]: { value: msg.value, unit: msg.unit },
        }))
        break
      case 'attendance':
        setAttendance(prev => {
          const dup = prev.some(
            r => r.student_id === msg.student_id && r.session_id === msg.session_id
          )
          if (dup) return prev
          return [{ ...msg, detected_at: new Date().toISOString() }, ...prev]
        })
        break
      case 'alert':
        setAlerts(prev => [{ ...msg, created_at: new Date().toISOString() }, ...prev].slice(0, 50))
        break
    }
  }, [stopDemo])

  const connect = useCallback(() => {
    if (dead.current) return
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}${WS_PATH}`)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      backoff.current = INITIAL_BACKOFF
    }

    ws.onmessage = (e) => {
      try { handleMessage(JSON.parse(e.data)) } catch {}
    }

    ws.onclose = () => {
      setIsConnected(false)
      if (!dead.current) {
        retryTimer.current = setTimeout(() => {
          backoff.current = Math.min(backoff.current * 2, MAX_BACKOFF)
          connect()
        }, backoff.current)
      }
    }

    ws.onerror = () => ws.close()
  }, [handleMessage])

  // Demo mode watchdog: poll every 2s, activate after 8s with no real data
  useEffect(() => {
    const checker = setInterval(() => {
      if (dead.current || inDemoMode.current) return
      const last = lastMessageTime.current
      if (last == null || Date.now() - last > DEMO_TIMEOUT_MS) {
        startDemo()
      }
    }, 2_000)
    return () => clearInterval(checker)
  }, [startDemo])

  useEffect(() => {
    dead.current = false
    connect()
    return () => {
      dead.current = true
      clearTimeout(retryTimer.current)
      wsRef.current?.close()
      if (demoInterval.current) clearInterval(demoInterval.current)
    }
  }, [connect])

  return { sensors, attendance, alerts, relayStatus, isConnected, isDemoMode }
}
