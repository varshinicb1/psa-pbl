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
          <svg className="logo-svg" viewBox="0 0 24 24" width="22" height="22" fill="none">
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="url(#lg)" />
            <defs>
              <linearGradient id="lg" x1="0" y1="0" x2="24" y2="24">
                <stop offset="0%" stopColor="#45d19a" />
                <stop offset="100%" stopColor="#5b9cf5" />
              </linearGradient>
            </defs>
          </svg>
          <span className="logo-text">Metro Grid</span>
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
