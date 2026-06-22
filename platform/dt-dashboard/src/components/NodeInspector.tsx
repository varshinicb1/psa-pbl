import type { GridNode } from '../types'
import { getNodeShortId, getNodeVoltageStatus } from '../types'
import { formatPu } from '../utils/format'

interface NodeInspectorProps {
  node: GridNode | null
  onClose: () => void
}

export function NodeInspector({ node, onClose }: NodeInspectorProps) {
  if (!node) return null

  const status = getNodeVoltageStatus(node)
  const vm = node.dynamic?.vm_pu as number | undefined
  const va = node.dynamic?.va_degree as number | undefined
  const p = node.dynamic?.p_mw as number | undefined
  const q = node.dynamic?.q_mvar as number | undefined
  const vn = node.static?.vn_kv as number | undefined
  const shortId = getNodeShortId(node)

  const statusLabel = status === 'high' ? 'Over Voltage' : status === 'low' ? 'Under Voltage' : 'Normal'

  return (
    <div className="inspector-overlay" onClick={onClose}>
      <div className="inspector-panel" onClick={e => e.stopPropagation()}>
        <div className="inspector-header">
          <h3 className="inspector-title">{shortId}</h3>
          <button className="inspector-close" onClick={onClose}>✕</button>
        </div>
        <div className="inspector-body">
          <div className="inspector-section">
            <div className="inspector-section-title">Status</div>
            <div className="inspector-badge-row">
              <span className={`status-badge badge-${status}`}>{statusLabel}</span>
              <span className="status-badge badge-type">{node.type}</span>
            </div>
          </div>
          <div className="inspector-section">
            <div className="inspector-section-title">Electrical</div>
            <div className="inspector-grid">
              {vm !== undefined && (
                <div className="inspector-field">
                  <span className="field-label">Voltage</span>
                  <span className={`field-value ${status !== 'normal' ? 'text-danger' : ''}`}>
                    {formatPu(vm)} p.u.
                  </span>
                </div>
              )}
              {va !== undefined && (
                <div className="inspector-field">
                  <span className="field-label">Angle</span>
                  <span className="field-value">{va.toFixed(2)}°</span>
                </div>
              )}
              {p !== undefined && (
                <div className="inspector-field">
                  <span className="field-label">Active Power</span>
                  <span className="field-value">{p.toFixed(2)} MW</span>
                </div>
              )}
              {q !== undefined && (
                <div className="inspector-field">
                  <span className="field-label">Reactive Power</span>
                  <span className="field-value">{q.toFixed(2)} MVAr</span>
                </div>
              )}
            </div>
          </div>
          <div className="inspector-section">
            <div className="inspector-section-title">Configuration</div>
            <div className="inspector-grid">
              {vn !== undefined && (
                <div className="inspector-field">
                  <span className="field-label">Nominal Voltage</span>
                  <span className="field-value">{vn} kV</span>
                </div>
              )}
              <div className="inspector-field">
                <span className="field-label">Full ID</span>
                <span className="field-value field-mono">{node.id}</span>
              </div>
              {node.substation_id && (
                <div className="inspector-field">
                  <span className="field-label">Substation</span>
                  <span className="field-value">{node.substation_id}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
