import { useState, useCallback } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { ErrorBoundary } from './components/ErrorBoundary'
import { StatusBar } from './components/StatusBar'
import { QuickStats } from './components/QuickStats'
import { TopologyMap } from './components/TopologyMap'
import { VoltageChart } from './components/VoltageChart'
import { AnomalyPanel } from './components/AnomalyPanel'
import { TimelineChart } from './components/TimelineChart'
import { NodeInspector } from './components/NodeInspector'
import type { GridNode } from './types'

export default function App() {
  const { connected, tickCount, snapshot, explanation, error, tickHistory, lastUpdate, refresh } = useWebSocket()
  const [selectedNode, setSelectedNode] = useState<GridNode | null>(null)

  const handleNodeSelect = useCallback((node: GridNode) => {
    setSelectedNode(node)
  }, [])

  const handleNodeInspectorClose = useCallback(() => {
    setSelectedNode(null)
  }, [])

  return (
    <ErrorBoundary>
      <div className="app">
        <StatusBar
          connected={connected}
          tickCount={tickCount}
          snapshot={snapshot}
          error={error}
          lastUpdate={lastUpdate}
          onRefresh={refresh}
        />
        {error && !connected && (
          <div className="error-banner">
            <span className="error-icon">!</span>
            <span className="error-text">{error}</span>
            <button className="error-dismiss" onClick={refresh}>Retry</button>
          </div>
        )}
        <div className="dashboard-grid">
          <div className="grid-left">
            <QuickStats snapshot={snapshot} tickHistory={tickHistory} />
            <TopologyMap snapshot={snapshot} onNodeSelect={handleNodeSelect} />
          </div>
          <div className="grid-center">
            <VoltageChart snapshot={snapshot} />
            <TimelineChart tickHistory={tickHistory} tickCount={tickCount} />
          </div>
          <div className="grid-right">
            <AnomalyPanel explanation={explanation} />
          </div>
        </div>
        <NodeInspector node={selectedNode} onClose={handleNodeInspectorClose} />
        <footer className="academic-footer">
          <strong>RV College of Engineering®</strong>
          <span className="footer-divider" />
          <span>Dept. of Electrical Engineering</span>
          <span className="footer-divider" />
          <span>Power System Analysis | PBL 2026</span>
          <span className="footer-divider" />
          <span>Guided by Dr. Manjunatha C.</span>
        </footer>
      </div>
    </ErrorBoundary>
  )
}
