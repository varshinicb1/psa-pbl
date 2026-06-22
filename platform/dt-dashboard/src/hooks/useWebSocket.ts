import { useEffect, useRef, useState, useCallback } from 'react'
import type { TickEntry, DashboardState, GridSnapshot, ExplanationPacket } from '../types'
import { WS_RECONNECT_BASE_MS, WS_RECONNECT_MAX_MS, WS_RECONNECT_JITTER, TICK_HISTORY_MAX, POLL_INTERVAL_MS } from '../types'

function getWsBase(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = import.meta.env.VITE_WS_HOST || window.location.host
  const path = import.meta.env.VITE_WS_PATH || '/ws'
  return `${proto}://${host}${path}`
}

function getApiBase(): string {
  return import.meta.env.VITE_API_BASE || '/api'
}

export function useWebSocket() {
  const [state, setState] = useState<DashboardState>({
    connected: false,
    tickCount: 0,
    snapshot: null,
    explanation: null,
    error: null,
    tickHistory: [],
    lastUpdate: null,
  })

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttempt = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null)
  const intentionalClose = useRef(false)
  const stateRef = useRef(state)
  stateRef.current = state

  const update = useCallback((partial: Partial<DashboardState>) => {
    setState(prev => ({ ...prev, ...partial }))
  }, [])

  const bringSnapshot = useCallback(async () => {
    try {
      const res = await fetch(`${getApiBase()}/snapshot`, { signal: AbortSignal.timeout(5000) })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: GridSnapshot = await res.json()
      update({ snapshot: data, error: null, lastUpdate: Date.now() })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      if (!stateRef.current.connected) {
        update({ error: `Snapshot fetch: ${msg}` })
      }
    }
  }, [update])

  const scheduleReconnect = useCallback(() => {
    if (intentionalClose.current) return
    const attempt = reconnectAttempt.current
    const delay = Math.min(
      WS_RECONNECT_BASE_MS * Math.pow(2, attempt),
      WS_RECONNECT_MAX_MS
    ) * (1 + (Math.random() - 0.5) * WS_RECONNECT_JITTER * 2)

    reconnectTimer.current = setTimeout(() => {
      reconnectAttempt.current = attempt + 1
      connect()
    }, delay)
  }, [])

  const connect = useCallback(() => {
    if (intentionalClose.current) return
    try {
      const ws = new WebSocket(getWsBase())
      wsRef.current = ws

      ws.onopen = () => {
        reconnectAttempt.current = 0
        update({ connected: true, error: null })
      }

      ws.onclose = () => {
        if (wsRef.current === ws) {
          wsRef.current = null
          update({ connected: false })
          scheduleReconnect()
        }
      }

      ws.onerror = () => {
        if (wsRef.current === ws) {
          update({ error: 'WebSocket connection error' })
        }
      }

      ws.onmessage = (ev: MessageEvent) => {
        let msg: Record<string, unknown>
        try { msg = JSON.parse(ev.data) } catch { return }

        if (msg.type === 'snapshot' && msg.payload && typeof msg.payload === 'object') {
          update({ snapshot: msg.payload as GridSnapshot, lastUpdate: Date.now() })
        } else if (msg.type === 'tick' && msg.snapshot && typeof msg.snapshot === 'object') {
          const tick = typeof msg.tick === 'number' ? msg.tick : 0
          const snapshot = msg.snapshot as GridSnapshot
          const rawExplanation = msg.explanation
          const explanation: ExplanationPacket | null =
            rawExplanation && typeof rawExplanation === 'object'
              ? (rawExplanation as ExplanationPacket)
              : null
          const entry: TickEntry = {
            tick,
            anomalies: explanation?.explanations?.length ?? 0,
            timestamp: Date.now(),
          }
          setState(prev => ({
            ...prev,
            tickCount: prev.tickCount + 1,
            snapshot,
            explanation,
            lastUpdate: Date.now(),
            tickHistory: [...prev.tickHistory.slice(-(TICK_HISTORY_MAX - 1)), entry],
          }))
        } else if (msg.type === 'heartbeat') {
          update({ lastUpdate: Date.now() })
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      update({ error: `WebSocket connect: ${msg}` })
      scheduleReconnect()
    }
  }, [update, scheduleReconnect])

  const refresh = useCallback(() => {
    bringSnapshot()
  }, [bringSnapshot])

  useEffect(() => {
    connect()
    bringSnapshot()
    pollTimer.current = setInterval(bringSnapshot, POLL_INTERVAL_MS)

    return () => {
      intentionalClose.current = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (pollTimer.current) clearInterval(pollTimer.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect, bringSnapshot])

  return { ...state, refresh }
}
