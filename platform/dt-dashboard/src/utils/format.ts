export function formatTimestamp(ts: string | number | null | undefined): string {
  if (ts === null || ts === undefined) return '--'
  const d = typeof ts === 'number' ? new Date(ts) : new Date(ts)
  if (isNaN(d.getTime())) return '--'
  return d.toLocaleTimeString('en-IN', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function formatDateTime(ts: string | number | null | undefined): string {
  if (ts === null || ts === undefined) return '--'
  const d = typeof ts === 'number' ? new Date(ts) : new Date(ts)
  if (isNaN(d.getTime())) return '--'
  return d.toLocaleString('en-IN', {
    hour12: false, year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

export function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toLocaleString('en-IN')
}

export function formatPercent(n: number, decimals = 1): string {
  return `${n.toFixed(decimals)}%`
}

export function formatPu(v: number, decimals = 4): string {
  return v.toFixed(decimals)
}

export function timeAgo(ts: number | null | undefined): string {
  if (!ts) return 'never'
  const sec = Math.floor((Date.now() - ts) / 1000)
  if (sec < 5) return 'just now'
  if (sec < 60) return `${sec}s ago`
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`
  return `${Math.floor(sec / 3600)}h ago`
}
