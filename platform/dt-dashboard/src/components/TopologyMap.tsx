import { memo, useMemo } from 'react'
import type { GridSnapshot, GridNode, GridEdge } from '../types'
import { getNodeShortId, getNodeVoltageStatus, getEdgeStatus } from '../types'

interface TopologyMapProps {
  snapshot: GridSnapshot | null
  onNodeSelect: (node: GridNode) => void
}

interface LayoutNode {
  node: GridNode
  x: number
  y: number
  id: string
}

interface LayoutEdge {
  edge: GridEdge
  x1: number
  y1: number
  x2: number
  y2: number
}

const SVG_W = 800
const SVG_H = 450
const PAD_X = 50
const PAD_Y = 50
const COLS = 7

function computeLayout(snapshot: GridSnapshot): { nodes: LayoutNode[]; edges: LayoutEdge[] } {
  const nodeMap = new Map(snapshot.nodes.map(n => [n.id, n]))
  const layoutNodes = snapshot.nodes.map(n => {
    const idx = parseInt(getNodeShortId(n)) || 0
    return {
      node: n,
      x: PAD_X + (idx % COLS) / (COLS - 1) * (SVG_W - 2 * PAD_X),
      y: PAD_Y + Math.floor(idx / COLS) * 50,
      id: n.id,
    }
  })
  const layoutEdges = snapshot.edges
    .map(e => {
      const src = nodeMap.get(e.source)
      const tgt = nodeMap.get(e.target)
      if (!src || !tgt) return null
      const s = layoutNodes.find(n => n.id === e.source)
      const t = layoutNodes.find(n => n.id === e.target)
      if (!s || !t) return null
      return { edge: e, x1: s.x, y1: s.y, x2: t.x, y2: t.y }
    })
    .filter((e): e is LayoutEdge => e !== null)
  return { nodes: layoutNodes, edges: layoutEdges }
}

const NodeCircle = memo(function NodeCircle({ node, x, y, onSelect }: LayoutNode & { onSelect: (n: GridNode) => void }) {
  const status = getNodeVoltageStatus(node)
  const shortId = getNodeShortId(node)
  const vm = node.dynamic?.vm_pu as number | undefined
  const fillColor = status === 'high' ? '#ff5c7a' : status === 'low' ? '#ffb347' : '#45d19a'
  const strokeColor = status === 'high' ? '#ff1744' : status === 'low' ? '#ff9100' : '#1b5e20'
  const r = status !== 'normal' ? 7 : 5

  return (
    <g
      className="topo-node"
      onClick={() => onSelect(node)}
      style={{ cursor: 'pointer' }}
    >
      <title>{`${shortId}\nV: ${vm?.toFixed(4) ?? '--'} p.u.\nStatus: ${status}`}</title>
      <circle
        cx={x} cy={y} r={r * 1.8}
        fill="transparent"
        stroke="transparent"
        strokeWidth={6}
      />
      <circle
        cx={x} cy={y} r={r}
        fill={fillColor}
        stroke={strokeColor}
        strokeWidth={1.5}
        className="topo-node-circle"
      />
      {status !== 'normal' && (
        <circle
          cx={x} cy={y} r={r * 2}
          fill="none"
          stroke={fillColor}
          strokeWidth={1}
          strokeDasharray="2 2"
          opacity={0.5}
        />
      )}
      <text
        x={x} y={y - r - 6}
        textAnchor="middle"
        fill="#a6b2ca"
        fontSize="9"
        fontFamily="var(--font-mono, monospace)"
        className="topo-node-label"
      >
        {shortId}
      </text>
      {vm !== undefined && (
        <text
          x={x} y={y + r + 14}
          textAnchor="middle"
          fill={status === 'normal' ? '#6b7a9a' : fillColor}
          fontSize="7"
          fontFamily="var(--font-mono, monospace)"
        >
          {vm.toFixed(3)}
        </text>
      )}
    </g>
  )
})

const EdgeLine = memo(function EdgeLine({ edge, x1, y1, x2, y2 }: LayoutEdge) {
  const status = getEdgeStatus(edge)
  const color = status === 'critical' ? '#ff5c7a' : status === 'warning' ? '#ffb347' : '#3a4a6a'
  const width = status === 'critical' ? 2.5 : status === 'warning' ? 2 : 1.2
  const loading = edge.dynamic?.loading_percent as number | undefined

  const midX = (x1 + x2) / 2
  const midY = (y1 + y2) / 2

  return (
    <g>
      <line
        x1={x1} y1={y1} x2={x2} y2={y2}
        stroke={color}
        strokeWidth={width}
        strokeOpacity={status === 'normal' ? 0.4 : 0.8}
        className="topo-edge"
      />
      {status !== 'normal' && loading !== undefined && (
        <g>
          <rect
            x={midX - 16} y={midY - 7}
            width={32} height={14} rx={3}
            fill="rgba(7,11,20,0.85)"
            stroke={color}
            strokeWidth={0.5}
          />
          <text
            x={midX} y={midY + 4}
            textAnchor="middle"
            fill={color}
            fontSize="8"
            fontFamily="var(--font-mono, monospace)"
          >
            {loading.toFixed(0)}%
          </text>
        </g>
      )}
    </g>
  )
})

export const TopologyMap = memo(function TopologyMap({ snapshot, onNodeSelect }: TopologyMapProps) {
  const layout = useMemo(() => {
    if (!snapshot) return null
    return computeLayout(snapshot)
  }, [snapshot])

  if (!layout) {
    return (
      <div className="panel panel-map">
        <h3 className="panel-title">Grid Topology</h3>
        <div className="map-empty">
          <div className="map-empty-icon">◉</div>
          <div className="map-empty-text">Waiting for grid data...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="panel panel-map">
      <h3 className="panel-title">
        Grid Topology
        <span className="topo-hash" title={`Hash: ${snapshot!.topology_hash}`}>
          #{snapshot!.topology_hash.slice(0, 10)}
        </span>
        <span className="topo-version">v{snapshot!.topology_version}</span>
      </h3>
      <div className="topo-container">
        <svg viewBox={`0 0 ${SVG_W} ${SVG_H}`} className="topo-svg" preserveAspectRatio="xMidYMid meet">
          <defs>
            <filter id="glow">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          {layout.edges.map(e => (
            <EdgeLine key={e.edge.id} {...e} />
          ))}
          {layout.nodes.map(n => (
            <NodeCircle key={n.node.id} {...n} onSelect={onNodeSelect} />
          ))}
        </svg>
      </div>
    </div>
  )
})
