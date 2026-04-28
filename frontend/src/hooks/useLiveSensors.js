import { useState, useEffect, useRef, useCallback } from 'react'

const WS_PATH = '/ws/classroom/room1'
const INITIAL_BACKOFF = 3_000
const MAX_BACKOFF = 30_000

export default function useLiveSensors() {
  const [sensors, setSensors]         = useState({})
  const [attendance, setAttendance]   = useState([])
  const [alerts, setAlerts]           = useState([])
  const [relayStatus, setRelayStatus] = useState({ ac: 'auto', lighting: 'auto' })
  const [isConnected, setIsConnected] = useState(false)

  const wsRef      = useRef(null)
  const backoff    = useRef(INITIAL_BACKOFF)
  const retryTimer = useRef(null)
  const dead       = useRef(false)

  const handleMessage = useCallback((msg) => {
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
  }, [])

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

  useEffect(() => {
    dead.current = false
    connect()
    return () => {
      dead.current = true
      clearTimeout(retryTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { sensors, attendance, alerts, relayStatus, isConnected }
}
