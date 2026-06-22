export interface GridNode {
  id: string
  type: string
  static: Record<string, number | string | boolean>
  dynamic: Record<string, number | string | boolean | null>
  coordinates?: { latitude: number; longitude: number }
  substation_id?: string
}

export interface GridEdge {
  id: string
  type: string
  source: string
  target: string
  static: Record<string, number | string | boolean>
  dynamic: Record<string, number | string | boolean | null>
}

export interface GridSnapshot {
  t: string
  topology_hash: string
  topology_version: number
  tick_count: number
  nodes: GridNode[]
  edges: GridEdge[]
  metadata: Record<string, string | number | boolean>
}

export interface NodeScore {
  id: string
  score: number
}

export interface EdgeScore {
  id: string
  score: number
}

export interface Explanation {
  type: string
  node_scores: NodeScore[]
  edge_scores: EdgeScore[]
}

export interface ExplanationPacket {
  model_version: string
  target: { type: string }
  uncertainty: { mode: string }
  explanations: Explanation[]
  ml_confidence?: number
}

export interface TickEntry {
  tick: number
  anomalies: number
  timestamp: number
}

export type WsMessage =
  | { type: 'snapshot'; payload: GridSnapshot }
  | { type: 'tick'; tick: number; snapshot: GridSnapshot; explanation: ExplanationPacket | null }
  | { type: 'heartbeat' }
  | Record<string, unknown>

export interface DashboardState {
  connected: boolean
  tickCount: number
  snapshot: GridSnapshot | null
  explanation: ExplanationPacket | null
  error: string | null
  tickHistory: TickEntry[]
  lastUpdate: number | null
}

export const WS_RECONNECT_BASE_MS = 500
export const WS_RECONNECT_MAX_MS = 30000
export const WS_RECONNECT_JITTER = 0.3
export const POLL_INTERVAL_MS = 30000
export const TICK_HISTORY_MAX = 200

export const VOLTAGE_MIN = 0.90
export const VOLTAGE_MAX = 1.10
export const VOLTAGE_LOWER_BOUND = 0.95
export const VOLTAGE_UPPER_BOUND = 1.05
export const LOADING_WARNING = 80
export const LOADING_CRITICAL = 95

export function getNodeShortId(node: GridNode): string {
  return node.id.split('/').pop() ?? node.id
}

export function getVoltageViolations(nodes: GridNode[]): number {
  return nodes.filter(n => {
    const v = n.dynamic?.vm_pu as number | undefined
    return v !== undefined && (v < VOLTAGE_LOWER_BOUND || v > VOLTAGE_UPPER_BOUND)
  }).length
}

export function getAverageVoltage(nodes: GridNode[]): number {
  const voltages = nodes.map(n => n.dynamic?.vm_pu as number | undefined).filter((v): v is number => v !== undefined)
  return voltages.length > 0 ? voltages.reduce((a, b) => a + b, 0) / voltages.length : 0
}

export function getMaxLoading(edges: GridEdge[]): number {
  const loadings = edges.map(e => e.dynamic?.loading_percent as number | undefined).filter((v): v is number => v !== undefined)
  return loadings.length > 0 ? Math.max(...loadings) : 0
}

export function getEdgeStatus(edge: GridEdge): 'normal' | 'warning' | 'critical' {
  const loading = edge.dynamic?.loading_percent as number | undefined
  if (!loading) return 'normal'
  if (loading >= LOADING_CRITICAL) return 'critical'
  if (loading >= LOADING_WARNING) return 'warning'
  return 'normal'
}

export function getNodeVoltageStatus(node: GridNode): 'normal' | 'low' | 'high' {
  const v = node.dynamic?.vm_pu as number | undefined
  if (!v) return 'normal'
  if (v < VOLTAGE_LOWER_BOUND) return 'low'
  if (v > VOLTAGE_UPPER_BOUND) return 'high'
  return 'normal'
}
