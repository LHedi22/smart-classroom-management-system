import { useState, useEffect } from 'react'
import { useSensor } from '../context/SensorContext'
import client from '../api/client'

const ROOM_ID = 'room1'

function ToggleCard({ title, device, value, onChange, description }) {
  const opts = ['on', 'off', 'auto']
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-white">{title}</h3>
          <p className="text-xs text-gray-500 mt-0.5">{description}</p>
        </div>
        <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
          value === 'on'   ? 'bg-green-900 text-green-300' :
          value === 'off'  ? 'bg-gray-700 text-gray-300' :
          'bg-indigo-900 text-indigo-300'
        }`}>
          {value}
        </span>
      </div>
      <div className="flex rounded-lg overflow-hidden border border-gray-700">
        {opts.map(opt => (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            className={`flex-1 py-2.5 text-sm font-medium capitalize transition-colors ${
              value === opt
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function Control() {
  const { sensors } = useSensor()
  const [relay, setRelay]       = useState({ ac: 'auto', lighting: 'auto' })
  const [actionLog, setActionLog] = useState([])

  useEffect(() => {
    client.get(`/control/status/${ROOM_ID}`).then(r => {
      setRelay({ ac: r.data.ac, lighting: r.data.lighting })
    }).catch(() => {})
  }, [])

  async function sendCommand(device, action) {
    const prev = relay[device]
    setRelay(r => ({ ...r, [device]: action }))
    try {
      await client.post(`/control/${device}`, { room_id: ROOM_ID, action })
      setActionLog(log => [{
        device,
        action,
        ts: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      }, ...log].slice(0, 10))
    } catch {
      setRelay(r => ({ ...r, [device]: prev }))
    }
  }

  const temp = sensors.temperature?.value
  const hum  = sensors.humidity?.value
  const aq   = sensors.air_quality?.value

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-xl font-bold text-white">Control</h1>

      {/* Current readings */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Temperature', value: temp != null ? `${temp.toFixed(1)}°C` : '—' },
          { label: 'Humidity',    value: hum  != null ? `${hum.toFixed(0)}%`   : '—' },
          { label: 'Air Quality', value: aq   != null ? `${aq.toFixed(0)} ppm` : '—' },
        ].map(({ label, value }) => (
          <div key={label} className="bg-gray-800 rounded-xl px-4 py-3 flex items-center gap-3">
            <div>
              <p className="text-xs text-gray-400">{label}</p>
              <p className="text-xl font-bold text-white">{value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Controls */}
      <div className="grid grid-cols-2 gap-4">
        <ToggleCard
          title="Air Conditioning"
          device="ac"
          value={relay.ac}
          onChange={v => sendCommand('ac', v)}
          description="Auto: turns on above 28°C, off below 22°C"
        />
        <ToggleCard
          title="Lighting"
          device="lighting"
          value={relay.lighting}
          onChange={v => sendCommand('lighting', v)}
          description="Manual override or automatic schedule"
        />
      </div>

      {/* Action log */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-800">
          <h2 className="text-sm font-semibold text-white">Action Log</h2>
        </div>
        {actionLog.length === 0 ? (
          <p className="text-center text-gray-600 text-sm py-8">No actions yet</p>
        ) : (
          <ul className="divide-y divide-gray-800">
            {actionLog.map((entry, i) => (
              <li key={i} className="px-4 py-3 flex items-center gap-3 text-sm">
                <span className="text-gray-500 font-mono text-xs w-20 shrink-0">{entry.ts}</span>
                <span className="text-gray-300 capitalize">{entry.device}</span>
                <span className="text-gray-500">→</span>
                <span className={`font-medium ${
                  entry.action === 'on'   ? 'text-green-400' :
                  entry.action === 'off'  ? 'text-red-400' :
                  'text-indigo-400'
                }`}>{entry.action}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
