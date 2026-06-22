import { memo, useMemo } from 'react'
import type { GridSnapshot } from '../types'
import { VOLTAGE_LOWER_BOUND, VOLTAGE_UPPER_BOUND, VOLTAGE_MIN, VOLTAGE_MAX, getNodeShortId } from '../types'

interface VoltageChartProps {
  snapshot: GridSnapshot | null
}

interface BarData {
  id: string
  vm_pu: number
  violation: boolean
}

export const VoltageChart = memo(function VoltageChart({ snapshot }: VoltageChartProps) {
  const bars = useMemo(() => {
    if (!snapshot) return [] as BarData[]
    return snapshot.nodes
      .map(n => ({
        id: getNodeShortId(n),
        vm_pu: (n.dynamic?.vm_pu as number) ?? 0,
        violation: false,
      }))
      .filter(n => n.vm_pu > 0)
      .sort((a, b) => a.vm_pu - b.vm_pu)
      .map(b => ({ ...b, violation: b.vm_pu < VOLTAGE_LOWER_BOUND || b.vm_pu > VOLTAGE_UPPER_BOUND }))
  }, [snapshot])

  const range = VOLTAGE_MAX - VOLTAGE_MIN
  const barHeight = (v: number) => ((v - VOLTAGE_MIN) / range) * 100

  return (
    <div className="panel panel-chart">
      <h3 className="panel-title">
        Bus Voltages (p.u.)
        <span className="chart-legend">
          <span className="legend-item"><span className="legend-swatch swatch-normal" /> Normal</span>
          <span className="legend-item"><span className="legend-swatch swatch-violation" /> Violation</span>
        </span>
      </h3>
      <div className="chart-container">
        <div className="chart-y-axis">
          <span>1.10</span>
          <span>1.05</span>
          <span>1.00</span>
          <span>0.95</span>
          <span>0.90</span>
        </div>
        <div className="chart-main">
          <div className="chart-violation-zones">
            <div className="zone-high" style={{ bottom: `${barHeight(VOLTAGE_UPPER_BOUND)}%`, top: '0' }} />
            <div className="zone-low" style={{ top: `${100 - barHeight(VOLTAGE_LOWER_BOUND)}%`, bottom: '0' }} />
          </div>
          <div className="chart-threshold-line line-upper" style={{ bottom: `${barHeight(VOLTAGE_UPPER_BOUND)}%` }} />
          <div className="chart-threshold-line line-nominal" style={{ bottom: `${barHeight(1.0)}%` }} />
          <div className="chart-threshold-line line-lower" style={{ bottom: `${barHeight(VOLTAGE_LOWER_BOUND)}%` }} />
          <div className="chart-bars">
            {bars.map(b => (
              <div
                key={b.id}
                className="chart-bar-group"
                title={`${b.id}: ${b.vm_pu.toFixed(4)} p.u.${b.violation ? ' ⚠ VIOLATION' : ''}`}
              >
                <div
                  className={`chart-bar ${b.violation ? 'bar-violation' : 'bar-normal'}`}
                  style={{ height: `${Math.max(barHeight(b.vm_pu), 2)}%` }}
                />
                <span className="chart-bar-label">{b.id}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
})
