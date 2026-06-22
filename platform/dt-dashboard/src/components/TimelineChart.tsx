import { memo, useMemo } from 'react'
import type { TickEntry } from '../types'

interface TimelineChartProps {
  tickHistory: TickEntry[]
  tickCount: number
}

export const TimelineChart = memo(function TimelineChart({ tickHistory }: TimelineChartProps) {
  const bars = useMemo(() => {
    if (tickHistory.length === 0) return [] as { anomaly: boolean; height: number }[]
    const maxAnomalies = Math.max(...tickHistory.map(t => t.anomalies), 1)
    return tickHistory.map(t => ({
      anomaly: t.anomalies > 0,
      height: Math.max((t.anomalies / maxAnomalies) * 48, t.anomalies > 0 ? 4 : 1),
    }))
  }, [tickHistory])

  return (
    <div className="panel panel-timeline">
      <h3 className="panel-title">
        Tick Timeline
        <span className="timeline-count">{tickHistory.length} samples</span>
      </h3>
      <div className="timeline-container">
        {bars.length === 0 ? (
          <div className="timeline-empty">No tick data yet</div>
        ) : (
          <div className="timeline-bars">
            {bars.map((b, i) => (
              <div
                key={i}
                className={`timeline-bar ${b.anomaly ? 'bar-anomaly' : 'bar-normal'}`}
                style={{ height: `${b.height}px` }}
                title={`Tick ${tickHistory[i]?.tick ?? i}: ${tickHistory[i]?.anomalies ?? 0} anomalies`}
              />
            ))}
          </div>
        )}
        <div className="timeline-footer">
          <span className="timeline-legend">
            <span className="legend-dot dot-normal" /> Normal
          </span>
          <span className="timeline-legend">
            <span className="legend-dot dot-anomaly" /> Anomaly
          </span>
        </div>
      </div>
    </div>
  )
})
