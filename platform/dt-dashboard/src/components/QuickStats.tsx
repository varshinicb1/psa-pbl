import { memo, useMemo } from 'react'
import type { GridSnapshot, TickEntry } from '../types'
import { getAverageVoltage, getVoltageViolations, getMaxLoading, VOLTAGE_LOWER_BOUND, VOLTAGE_UPPER_BOUND } from '../types'
import { formatPu, formatPercent } from '../utils/format'

interface QuickStatsProps {
  snapshot: GridSnapshot | null
  tickHistory: TickEntry[]
}

export const QuickStats = memo(function QuickStats({ snapshot, tickHistory }: QuickStatsProps) {
  const stats = useMemo(() => {
    if (!snapshot) return null
    const nodes = snapshot.nodes
    const edges = snapshot.edges
    const avgV = getAverageVoltage(nodes)
    const maxL = getMaxLoading(edges)
    const violations = getVoltageViolations(nodes)
    const anomalyCount = tickHistory.reduce((s, t) => s + t.anomalies, 0)
    const anomalyRate = tickHistory.length > 0
      ? (tickHistory.filter(t => t.anomalies > 0).length / tickHistory.length) * 100
      : 0
    return { avgV, maxL, violations, anomalyCount, anomalyRate }
  }, [snapshot, tickHistory])

  if (!stats) {
    return (
      <div className="panel panel-stats">
        <h3 className="panel-title">System Summary</h3>
        <div className="stats-grid">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="stat-card stat-skeleton">
              <div className="skeleton-line skeleton-value" />
              <div className="skeleton-line skeleton-label" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  const avgOk = stats.avgV >= VOLTAGE_LOWER_BOUND && stats.avgV <= VOLTAGE_UPPER_BOUND

  return (
    <div className="panel panel-stats">
      <h3 className="panel-title">System Summary</h3>
      <div className="stats-grid">
        <div className="stat-card">
          <div className={`stat-value ${avgOk ? 'text-normal' : 'text-danger'}`}>
            {formatPu(stats.avgV)}
          </div>
          <div className="stat-label">Avg Voltage (p.u.)</div>
          <div className="stat-trend">
            <span className={`trend-dot ${avgOk ? 'dot-green' : 'dot-red'}`} />
            {avgOk ? 'Nominal' : 'Violation'}
          </div>
        </div>
        <div className="stat-card">
          <div className={`stat-value ${stats.maxL > 80 ? 'text-warning' : 'text-normal'}`}>
            {formatPercent(stats.maxL, 1)}
          </div>
          <div className="stat-label">Max Loading</div>
          <div className="stat-trend">
            <span className={`trend-dot ${stats.maxL > 95 ? 'dot-red' : stats.maxL > 80 ? 'dot-orange' : 'dot-green'}`} />
            {stats.maxL > 95 ? 'Critical' : stats.maxL > 80 ? 'Warning' : 'Normal'}
          </div>
        </div>
        <div className="stat-card">
          <div className={`stat-value ${stats.violations > 0 ? 'text-danger' : 'text-normal'}`}>
            {stats.violations}
          </div>
          <div className="stat-label">Voltage Violations</div>
          <div className="stat-trend">
            {stats.violations > 0 ? `${stats.violations} bus${stats.violations !== 1 ? 'es' : ''} out of band` : 'All in band'}
          </div>
        </div>
        <div className="stat-card">
          <div className={`stat-value ${stats.anomalyRate > 10 ? 'text-warning' : stats.anomalyCount > 0 ? 'text-normal' : 'text-normal'}`}>
            {formatPercent(stats.anomalyRate, 1)}
          </div>
          <div className="stat-label">Anomaly Rate</div>
          <div className="stat-trend">
            {stats.anomalyCount === 0 ? 'Clean' : `${stats.anomalyCount} total events`}
          </div>
        </div>
      </div>
    </div>
  )
})
