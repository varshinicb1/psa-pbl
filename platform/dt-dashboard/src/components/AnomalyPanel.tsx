import { memo, useState } from 'react'
import type { ExplanationPacket } from '../types'

interface AnomalyPanelProps {
  explanation: ExplanationPacket | null
}

export const AnomalyPanel = memo(function AnomalyPanel({ explanation }: AnomalyPanelProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (!explanation || !explanation.explanations || explanation.explanations.length === 0) {
    return (
      <div className="panel panel-anomaly">
        <h3 className="panel-title">Alarms</h3>
        <div className="anomaly-empty">
          <svg viewBox="0 0 20 20" width="20" height="20" className="anomaly-empty-icon">
            <circle cx="10" cy="10" r="8" fill="none" stroke="#45d19a" strokeWidth="1.5" />
            <path d="M6 10l3 3 5-5" fill="none" stroke="#45d19a" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <span>System nominal — no anomalies</span>
        </div>
      </div>
    )
  }

  const allNodeScores = explanation.explanations.flatMap(e => e.node_scores)
  const allEdgeScores = explanation.explanations.flatMap(e => e.edge_scores)
  const totalAlerts = allNodeScores.length + allEdgeScores.length
  const topNodeScores = allNodeScores.sort((a, b) => b.score - a.score).slice(0, 10)
  const topEdgeScores = allEdgeScores.sort((a, b) => b.score - a.score).slice(0, 5)

  return (
    <div className={`panel panel-anomaly ${totalAlerts > 0 ? 'has-alerts' : ''}`}>
      <h3 className="panel-title">
        Alarms
        <span className="alarm-badge">{totalAlerts}</span>
        {explanation.ml_confidence !== undefined && (
          <span className="ml-badge" title="ML model confidence">
            ML {(explanation.ml_confidence * 100).toFixed(0)}%
          </span>
        )}
      </h3>
      <div className="anomaly-list">
        {topNodeScores.map(s => {
          const shortId = s.id.split('/').pop() ?? s.id
          const isExpanded = expandedId === s.id
          const severity = s.score > 0.8 ? 'critical' : s.score > 0.5 ? 'warning' : 'info'

          return (
            <div
              key={s.id}
              className={`anomaly-row severity-${severity}`}
              onClick={() => setExpandedId(isExpanded ? null : s.id)}
            >
              <div className="anomaly-row-header">
                <span className={`severity-dot dot-${severity}`} />
                <span className="anomaly-bus">{shortId}</span>
                <span className="anomaly-type">Voltage</span>
                <span className="anomaly-score">{(s.score * 100).toFixed(0)}%</span>
              </div>
              {isExpanded && (
                <div className="anomaly-detail">
                  <div className="anomaly-detail-row">Bus: {s.id}</div>
                  <div className="anomaly-detail-row">Score: {(s.score * 100).toFixed(1)}%</div>
                  <div className="anomaly-detail-row">Model: {explanation.model_version}</div>
                </div>
              )}
            </div>
          )
        })}
        {topEdgeScores.map(s => {
          const shortId = s.id.split('/').pop() ?? s.id
          const isExpanded = expandedId === `edge-${s.id}`
          const severity = s.score > 80 ? 'critical' : s.score > 50 ? 'warning' : 'info'

          return (
            <div
              key={`edge-${s.id}`}
              className={`anomaly-row severity-${severity}`}
              onClick={() => setExpandedId(isExpanded ? null : `edge-${s.id}`)}
            >
              <div className="anomaly-row-header">
                <span className={`severity-dot dot-${severity}`} />
                <span className="anomaly-bus">{shortId}</span>
                <span className="anomaly-type">Overload</span>
                <span className="anomaly-score">{s.score.toFixed(0)}%</span>
              </div>
              {isExpanded && (
                <div className="anomaly-detail">
                  <div className="anomaly-detail-row">Line: {s.id}</div>
                  <div className="anomaly-detail-row">Loading: {s.score.toFixed(1)}%</div>
                  <div className="anomaly-detail-row">Model: {explanation.model_version}</div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
})
