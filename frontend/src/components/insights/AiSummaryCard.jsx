import { useEffect, useState } from 'react'
import client from '../../api/client'

const SparkleIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 3l1.88 5.76a1 1 0 0 0 .95.69h6.06l-4.9 3.56a1 1 0 0 0-.36 1.12L17.51 20 12 16.44 6.49 20l1.88-5.87a1 1 0 0 0-.36-1.12L3.11 9.45h6.06a1 1 0 0 0 .95-.69z"/>
  </svg>
)

const skeletonStyle = {
  background: 'var(--color-border)',
  borderRadius: 4,
  height: 14,
  animation: 'ai-pulse 1.4s ease-in-out infinite',
}

export default function AiSummaryCard({ scope, id, title = 'AI Summary' }) {
  const [state, setState] = useState('loading') // loading | success | error503 | error
  const [data, setData] = useState(null)

  useEffect(() => {
    if (!scope || !id) return
    setState('loading')
    client.get('/insights/ai-summary', { params: { scope, id } })
      .then(res => {
        setData(res.data)
        setState('success')
      })
      .catch(err => {
        const status = err?.response?.status
        setState(status === 503 ? 'error503' : 'error')
      })
  }, [scope, id])

  const cardStyle = {
    background: 'var(--color-surface)',
    border: '1px solid var(--color-border)',
    borderRadius: 12,
    padding: '20px 24px',
    boxShadow: 'var(--shadow-card)',
  }

  const headerStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
    color: 'var(--color-primary)',
  }

  const titleStyle = {
    fontFamily: "'DM Sans', sans-serif",
    fontWeight: 600,
    fontSize: 'var(--text-base)',
    color: 'var(--color-text-primary)',
    margin: 0,
  }

  return (
    <>
      <style>{`
        @keyframes ai-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>

      <div style={cardStyle}>
        <div style={headerStyle}>
          <SparkleIcon />
          <p style={titleStyle}>{title}</p>
        </div>

        {state === 'loading' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ ...skeletonStyle, width: '100%' }} />
            <div style={{ ...skeletonStyle, width: '88%' }} />
            <div style={{ ...skeletonStyle, width: '72%' }} />
          </div>
        )}

        {state === 'success' && data && (
          <>
            <p style={{
              fontFamily: "'Inter', sans-serif",
              fontWeight: 400,
              fontSize: 'var(--text-sm)',
              color: 'var(--color-text-primary)',
              lineHeight: 1.6,
              margin: 0,
            }}>
              {data.narrative}
            </p>
            {data.generated_at && (
              <p style={{
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-muted)',
                marginTop: 10,
                marginBottom: 0,
              }}>
                Generated at {new Date(data.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
            )}
          </>
        )}

        {state === 'error503' && (
          <p style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-muted)',
            margin: 0,
            fontStyle: 'italic',
          }}>
            Ollama is unreachable. Ensure it is running at <code>OLLAMA_BASE_URL</code> (default: <code>http://ollama:11434</code>).
          </p>
        )}

        {state === 'error' && (
          <p style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--color-text-muted)',
            margin: 0,
            fontStyle: 'italic',
          }}>
            Summary unavailable — check backend logs.
          </p>
        )}
      </div>
    </>
  )
}
