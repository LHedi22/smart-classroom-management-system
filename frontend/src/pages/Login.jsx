import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

// ── Brand mark ────────────────────────────────────────────────────────────

const BrandMark = () => (
  <svg width="36" height="36" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="36" height="36" rx="10" fill="var(--color-primary)"/>
    <rect x="8" y="14" width="20" height="2.5" rx="1.25" fill="white" opacity="0.9"/>
    <rect x="8" y="19.5" width="14" height="2.5" rx="1.25" fill="white" opacity="0.7"/>
    <circle cx="26" cy="24" r="4" fill="var(--color-teal)"/>
    <path d="M24 24l1.5 1.5L27.5 22.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

// ── Demo account row ───────────────────────────────────────────────────────

function DemoRow({ email, password, role, onFill }) {
  return (
    <button
      type="button"
      onClick={() => onFill(email, password)}
      style={{
        width: '100%',
        textAlign: 'left',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '9px 12px',
        borderRadius: 8,
        border: '1px solid var(--color-border)',
        background: 'var(--color-bg)',
        cursor: 'pointer',
        transition: 'background 0.12s ease, border-color 0.12s ease',
        outline: 'none',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.background = 'rgba(0,117,201,0.05)'
        e.currentTarget.style.borderColor = 'rgba(0,117,201,0.3)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = 'var(--color-bg)'
        e.currentTarget.style.borderColor = 'var(--color-border)'
      }}
    >
      <div>
        <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-primary)' }}>{email}</p>
        <p style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 1 }}>
          {password} · <span style={{ color: 'var(--color-primary)' }}>{role}</span>
        </p>
      </div>
      <span style={{ fontSize: 11, color: 'var(--color-text-muted)', flexShrink: 0 }}>click to fill →</span>
    </button>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function Login() {
  const { login }  = useAuth()
  const navigate   = useNavigate()

  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const body = new URLSearchParams({ username: email, password })
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || 'Invalid credentials')
        return
      }
      const data = await res.json()
      login(data)
      navigate('/dashboard', { replace: true })
    } catch {
      setError('Network error — is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  function fillDemo(e, p) {
    setEmail(e)
    setPassword(p)
    setError('')
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 24,
      background: 'var(--color-bg)',
    }}>
      <div style={{ width: '100%', maxWidth: 900, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, alignItems: 'start' }}>

        {/* ── Left: branding ───────────────────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 32, paddingTop: 8 }}>
          {/* Brand */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <BrandMark />
            <div>
              <p style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-primary)', textTransform: 'uppercase', letterSpacing: '0.12em', lineHeight: 1, marginBottom: 4 }}>
                SMU MedTech
              </p>
              <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)', letterSpacing: '-0.02em', lineHeight: 1 }}>
                Smart Classroom
              </p>
            </div>
          </div>

          {/* Tagline */}
          <div>
            <h1 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 32, fontWeight: 700, color: 'var(--color-text-primary)', letterSpacing: '-0.03em', lineHeight: 1.15, marginBottom: 12 }}>
              Professor<br/>Dashboard
            </h1>
            <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', lineHeight: 1.65, maxWidth: 300 }}>
              Manage attendance, monitor the classroom environment, and control devices — all in one place.
            </p>
          </div>

          {/* Feature list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[
              { label: 'Face recognition attendance', color: 'var(--color-green)' },
              { label: 'Live sensor monitoring',      color: 'var(--color-primary)' },
              { label: 'AC & lighting control',       color: 'var(--color-teal)' },
              { label: 'Moodle grade sync',           color: 'var(--color-purple)' },
            ].map(f => (
              <div key={f.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 7, height: 7, borderRadius: '50%', background: f.color, flexShrink: 0 }} />
                <span style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>{f.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Right: form + demo accounts ──────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Sign-in card */}
          <div className="glass-card">
            <h2 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 20, letterSpacing: '-0.02em' }}>
              Sign in
            </h2>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  placeholder="you@smu.tn"
                  className="field-control"
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="field-control"
                  style={{ width: '100%' }}
                />
              </div>

              {error && (
                <div style={{
                  fontSize: 13,
                  color: 'var(--color-red)',
                  background: 'rgba(236,0,68,0.06)',
                  border: '1px solid rgba(236,0,68,0.18)',
                  borderRadius: 8,
                  padding: '10px 14px',
                  fontWeight: 500,
                }}>
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="btn-primary"
                style={{ width: '100%', marginTop: 4, opacity: loading ? 0.65 : 1, cursor: loading ? 'not-allowed' : 'pointer' }}
              >
                {loading ? 'Signing in…' : 'Sign in'}
              </button>
            </form>
          </div>

          {/* Demo accounts card */}
          <div className="glass-card" style={{ padding: 16 }}>
            <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
              Demo accounts
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <DemoRow email="admin@smu.tn"       password="admin123" role="admin"     onFill={fillDemo} />
              <DemoRow email="s.trabelsi@smu.tn"  password="prof123"  role="professor" onFill={fillDemo} />
              <DemoRow email="l.chaabane@smu.tn"  password="prof123"  role="professor" onFill={fillDemo} />
            </div>
            <p style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 10, lineHeight: 1.5 }}>
              Run <code style={{ fontFamily: 'monospace', background: 'var(--color-border)', borderRadius: 4, padding: '1px 5px', fontSize: 11 }}>docker compose exec backend python seed.py</code> to populate demo data.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
