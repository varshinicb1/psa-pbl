import { memo } from 'react'
import type { GridSnapshot } from '../types'
import { timeAgo } from '../utils/format'

interface StatusBarProps {
  connected: boolean
  tickCount: number
  snapshot: GridSnapshot | null
  error: string | null
  lastUpdate: number | null
  onRefresh: () => void
}

export const StatusBar = memo(function StatusBar({
  connected, tickCount, snapshot, error, lastUpdate, onRefresh,
}: StatusBarProps) {
  const busCount = snapshot?.nodes?.length ?? 0
  const edgeCount = snapshot?.edges?.length ?? 0
  const tickDisplay = snapshot?.tick_count ?? tickCount

  return (
    <header className="status-bar">
      <div className="status-left">
        <div className="logo">
          {/* RVCE Academic Emblem — Book & Flame */}
          <svg className="logo-svg" viewBox="0 0 28 28" width="24" height="24" fill="none">
            <circle cx="14" cy="14" r="13" fill="#003D7A" stroke="#D4A01E" strokeWidth="1.5" />
            <path d="M8 17 Q10 10 14 9 Q18 10 20 17 L20 20 Q17 16 14 18 Q11 16 8 20Z" fill="#D4A01E" />
            <line x1="14" y1="9" x2="14" y2="18" stroke="#003D7A" strokeWidth="1.5" />
            <path d="M12 9 Q11 6 14 4 Q17 6 16 9 Q15 7 14 8 Q13 7 12 9Z" fill="#D4A01E" />
            <text x="14" y="25" textAnchor="middle" fontSize="6" fontWeight="bold" fill="#D4A01E">RVCE</text>
          </svg>
          <span className="logo-text">RVCE Metro Grid Twin</span>
        </div>
        <div className="status-indicators">
          <span className={`indicator ${connected ? 'online' : 'offline'}`} title={connected ? 'Connected' : 'Disconnected'}>
            <span className={`indicator-dot ${connected ? 'dot-online' : 'dot-offline'}`} />
            {connected ? 'LIVE' : 'OFFLINE'}
          </span>
          <span className="stat-item" title="Total ticks processed">
            <span className="stat-icon">⟳</span>
            {tickDisplay.toLocaleString()}
          </span>
          <span className="stat-divider" />
          <span className="stat-item" title="Grid buses">{busCount} buses</span>
          <span className="stat-item" title="Grid lines">{edgeCount} lines</span>
          <span className="stat-divider" />
          <span className="stat-item stat-time" title="Last update">
            {timeAgo(lastUpdate)}
          </span>
        </div>
      </div>
      <div className="status-right">
        {error && <span className="status-error" title={error}>!</span>}
        <span className="version-badge">v{import.meta.env.VITE_APP_VERSION || '2.0.0'}</span>
        <button className="btn-icon" onClick={onRefresh} title="Force refresh snapshot">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor">
            <path d="M8 0a8 8 0 00-8 8h2a6 6 0 1110.47 4H12v2h4V6h-2v1.76A8 8 0 008 0z" />
          </svg>
        </button>
      </div>
    </header>
  )
})
