import { useState, useEffect } from 'react'
import { useSensor } from '../context/SensorContext'
import client from '../api/client'

const ROOM_ID = 'room1'

// ── Device icons ─────────────────────────────────────────────────────────

const AcIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M8 15H3m5-6H3m18 6h-5m5-6h-5M9 9l3 3-3 3m6-6l-3 3 3 3M3 12h18"/>
  </svg>
)

const LightIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="2" x2="12" y2="6"/>
    <line x1="12" y1="18" x2="12" y2="22"/>
    <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/>
    <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/>
    <line x1="2" y1="12" x2="6" y2="12"/>
    <line x1="18" y1="12" x2="22" y2="12"/>
    <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/>
    <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/>
    <circle cx="12" cy="12" r="4"/>
  </svg>
)

const TempIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/>
  </svg>
)

const HumIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/>
  </svg>
)

const AqIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/>
    <path d="M9.6 4.6A2 2 0 1 1 11 8H2"/>
    <path d="M12.6 19.4A2 2 0 1 0 14 16H2"/>
  </svg>
)

// ── Relay state config ────────────────────────────────────────────────────

const STATE_CONFIG = {
  on:   { label: 'ON',   badgeClass: 'status-chip-success', btnActiveClass: 'relay-btn-on-active',   description: 'Running' },
  off:  { label: 'OFF',  badgeClass: 'status-chip-danger',  btnActiveClass: 'relay-btn-off-active',  description: 'Off' },
  auto: { label: 'AUTO', badgeClass: 'status-chip-neutral', btnActiveClass: 'relay-btn-auto-active', description: 'Automatic' },
}

function stateIconColor(value) {
  if (value === 'on')  return { bg: 'rgba(134,192,87,0.12)',  color: 'var(--color-forest)' }
  if (value === 'off') return { bg: 'rgba(236,0,68,0.08)',    color: 'var(--color-red)' }
  return                      { bg: 'rgba(0,117,201,0.09)',   color: 'var(--color-primary)' }
}

// ── Relay card ────────────────────────────────────────────────────────────

function RelayCard({ title, device, value, onChange }) {
  const Icon = device === 'ac' ? AcIcon : LightIcon
  const { bg, color } = stateIconColor(value)
  const cfg = STATE_CONFIG[value] ?? STATE_CONFIG.auto

  return (
    <div className="relay-card">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
        <div style={{
          width: 52, height: 52, borderRadius: 13,
          background: bg, color,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
          transition: 'background 0.3s ease, color 0.3s ease',
        }}>
          <Icon />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
            <h3 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 16, fontWeight: 700, color: 'var(--color-text-primary)' }}>
              {title}
            </h3>
            <span className={cfg.badgeClass} style={{ fontSize: 11, fontWeight: 700 }}>
              {cfg.label}
            </span>
          </div>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)', lineHeight: 1.45 }}>
            {cfg.description}
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="relay-btn-group">
        {['on', 'off', 'auto'].map(opt => (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            className={`relay-btn ${value === opt ? STATE_CONFIG[opt].btnActiveClass : ''}`}
          >
            {STATE_CONFIG[opt].label}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Sensor reading pill ───────────────────────────────────────────────────

function ReadingPill({ icon: Icon, label, value, iconColor, iconBg }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '14px 16px',
      borderRadius: 10,
      border: '1px solid var(--color-border)',
      background: 'var(--color-surface)',
    }}>
      <div style={{
        width: 38, height: 38, borderRadius: '50%',
        background: iconBg, color: iconColor,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon />
      </div>
      <div>
        <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', lineHeight: 1, marginBottom: 4 }}>{label}</p>
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 20, fontWeight: 700, color: 'var(--color-text-primary)', letterSpacing: '-0.02em', lineHeight: 1 }}>{value}</p>
      </div>
    </div>
  )
}

// ── Auto-mode info card ───────────────────────────────────────────────────

function AutoRuleCard() {
  return (
    <div style={{
      borderRadius: 12,
      border: '1px solid rgba(0,117,201,0.18)',
      background: 'rgba(0,117,201,0.04)',
      padding: '16px 20px',
    }}>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, fontWeight: 700, color: 'var(--color-primary)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        Auto-mode rules
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {[
          'AC turns on automatically when temperature exceeds 28 °C',
          'AC turns off automatically when temperature drops below 22 °C',
          'Air quality alert fires when CO₂ exceeds 500 ppm',
        ].map((rule, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--color-primary)', marginTop: 6, flexShrink: 0 }} />
            <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>{rule}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function Control() {
  const { sensors } = useSensor()
  const [relay,     setRelay]     = useState({ ac: 'auto', lighting: 'auto' })
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
    <div className="page-shell">
      {/* Page header */}
      <section className="page-header-card">
        <div className="page-header-row">
          <h1 className="section-title">Control</h1>
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 20, alignItems: 'start' }}>
        {/* Left: controls + readings */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Sensor readings */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
            <ReadingPill
              icon={TempIcon}
              label="Temperature"
              value={temp != null ? `${temp.toFixed(1)} °C` : '—'}
              iconBg="rgba(236,0,68,0.09)"
              iconColor="var(--color-red)"
            />
            <ReadingPill
              icon={HumIcon}
              label="Humidity"
              value={hum != null ? `${hum.toFixed(0)} %` : '—'}
              iconBg="rgba(0,117,201,0.09)"
              iconColor="var(--color-primary)"
            />
            <ReadingPill
              icon={AqIcon}
              label="CO₂"
              value={aq != null ? `${aq.toFixed(0)} ppm` : '—'}
              iconBg="rgba(255,183,0,0.1)"
              iconColor="#A07A00"
            />
          </div>

          {/* Relay cards */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <RelayCard
              title="Air Conditioning"
              device="ac"
              value={relay.ac}
              onChange={v => sendCommand('ac', v)}
            />
            <RelayCard
              title="Lighting"
              device="lighting"
              value={relay.lighting}
              onChange={v => sendCommand('lighting', v)}
            />
          </div>

          {/* Auto-mode rules */}
          <AutoRuleCard />
        </div>

        {/* Right: action log */}
        <div className="table-shell" style={{ height: '100%' }}>
          <div className="panel-header">
            <h2 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 14, fontWeight: 700, color: 'var(--color-text-primary)' }}>
              Action log
            </h2>
          </div>
          {actionLog.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                </svg>
              </div>
              <p className="empty-state-title">No actions yet</p>
              <p className="empty-state-desc">Commands you send will appear here.</p>
            </div>
          ) : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {actionLog.map((entry, i) => (
                <li key={i} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '10px 16px',
                  borderBottom: i < actionLog.length - 1 ? '1px solid var(--color-border)' : 'none',
                  fontSize: 13,
                }}>
                  <span style={{ color: 'var(--color-text-muted)', fontFamily: 'monospace', fontSize: 11, width: 58, flexShrink: 0 }}>{entry.ts}</span>
                  <span style={{ color: 'var(--color-text-secondary)', fontWeight: 600, textTransform: 'capitalize' }}>{entry.device}</span>
                  <span style={{ color: 'var(--color-border-strong)', fontSize: 11 }}>→</span>
                  <span style={{
                    fontWeight: 700,
                    color: entry.action === 'on' ? 'var(--color-forest)' : entry.action === 'off' ? 'var(--color-red)' : 'var(--color-primary)',
                    textTransform: 'uppercase',
                    fontSize: 11,
                    letterSpacing: '0.06em',
                  }}>{entry.action}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
