import { useEffect, useMemo, useRef, useState } from 'react'

type ExplanationPacket = any
type GridGraphSnapshot = any

type WsMessage =
  | { type: 'snapshot'; payload: GridGraphSnapshot }
  | { type: 'tick'; snapshot: GridGraphSnapshot; explanation: ExplanationPacket | null }
  | { type: string; [k: string]: any }

function jsonPreview(obj: unknown, maxChars = 4000): string {
  try {
    const s = JSON.stringify(obj, null, 2)
    return s.length > maxChars ? s.slice(0, maxChars) + '\n…(truncated)…' : s
  } catch {
    return String(obj)
  }
}

export default function App() {
  const [connected, setConnected] = useState(false)
  const [lastMsgAt, setLastMsgAt] = useState<string | null>(null)
  const [tickCount, setTickCount] = useState(0)
  const [snapshot, setSnapshot] = useState<GridGraphSnapshot | null>(null)
  const [explanation, setExplanation] = useState<ExplanationPacket | null>(null)
  const [error, setError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)

  const wsUrl = useMemo(() => {
    // In dev, Vite proxies /ws -> backend. In prod, you can serve this UI behind the same origin.
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${window.location.host}/ws`
  }, [])

  async function fetchSnapshot() {
    try {
      setError(null)
      const res = await fetch('/api/snapshot')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setSnapshot(data)
    } catch (e: any) {
      setError(`Failed to fetch /api/snapshot: ${e?.message ?? String(e)}`)
    }
  }

  useEffect(() => {
    let closedByUs = false

    function connect() {
      setError(null)
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
      }

      ws.onclose = () => {
        setConnected(false)
        wsRef.current = null
        if (!closedByUs) {
          // simple reconnect loop
          setTimeout(connect, 1000)
        }
      }

      ws.onerror = () => {
        setError('WebSocket error (see console for details).')
      }

      ws.onmessage = (ev) => {
        setLastMsgAt(new Date().toLocaleTimeString())
        let msg: WsMessage
        try {
          msg = JSON.parse(ev.data)
        } catch {
          return
        }

        if (msg.type === 'snapshot') {
          setSnapshot(msg.payload)
        } else if (msg.type === 'tick') {
          setTickCount((n) => n + 1)
          setSnapshot(msg.snapshot)
          setExplanation(msg.explanation ?? null)
        }
      }
    }

    connect()
    fetchSnapshot()

    return () => {
      closedByUs = true
      try {
        wsRef.current?.close()
      } catch {
        // ignore
      }
      wsRef.current = null
    }
  }, [wsUrl])

  const nodes = snapshot?.nodes?.length ?? 0
  const edges = snapshot?.edges?.length ?? 0
  const topoHash = snapshot?.topology_hash ?? '(none)'
  const topoVer = snapshot?.topology_version ?? '(none)'

  return (
    <div className="container">
      <header className="header">
        <div>
          <div className="title">Grid Digital Twin Dashboard (PoC)</div>
          <div className="subtitle">
            WS: <span className={connected ? 'ok' : 'bad'}>{connected ? 'connected' : 'disconnected'}</span> · last
            msg: {lastMsgAt ?? '—'} · ticks: {tickCount}
          </div>
        </div>
        <div className="actions">
          <button onClick={fetchSnapshot}>Fetch snapshot</button>
          <a className="link" href="/api/health" target="_blank" rel="noreferrer">
            API health
          </a>
          <a className="link" href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">
            Swagger docs
          </a>
        </div>
      </header>

      {error ? <div className="card error">{error}</div> : null}

      <main className="grid">
        <section className="card">
          <h2>Snapshot</h2>
          <div className="kv">
            <div>topology_hash</div>
            <div className="mono">{String(topoHash).slice(0, 16)}…</div>
            <div>topology_version</div>
            <div className="mono">{String(topoVer)}</div>
            <div>nodes</div>
            <div className="mono">{nodes}</div>
            <div>edges</div>
            <div className="mono">{edges}</div>
          </div>

          <details>
            <summary>Raw snapshot JSON</summary>
            <pre className="pre">{jsonPreview(snapshot)}</pre>
          </details>
        </section>

        <section className="card">
          <h2>Latest explanation</h2>
          {explanation ? (
            <>
              <div className="kv">
                <div>target</div>
                <div className="mono">{explanation?.target?.type ?? '(unknown)'}</div>
                <div>model_version</div>
                <div className="mono">{explanation?.model_version ?? '(unknown)'}</div>
                <div>uncertainty</div>
                <div className="mono">{explanation?.uncertainty?.mode ?? '(unknown)'}</div>
              </div>
              <details open>
                <summary>Top node scores</summary>
                <pre className="pre">
                  {jsonPreview(explanation?.explanations?.[0]?.node_scores ?? explanation?.explanations ?? explanation)}
                </pre>
              </details>
            </>
          ) : (
            <div className="muted">No explanation on the last tick (voltages within bounds).</div>
          )}
        </section>
      </main>

      <footer className="footer">
        Tip: keep the backend running at <span className="mono">127.0.0.1:8000</span>. This UI uses Vite proxy{' '}
        <span className="mono">/api</span> and <span className="mono">/ws</span>.
      </footer>
    </div>
  )
}

