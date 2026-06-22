import { describe, it, expect } from 'vitest'
import {
  getNodeShortId,
  getVoltageViolations,
  getAverageVoltage,
  getMaxLoading,
  getEdgeStatus,
  getNodeVoltageStatus,
  VOLTAGE_LOWER_BOUND,
  VOLTAGE_UPPER_BOUND,
  LOADING_WARNING,
  LOADING_CRITICAL,
} from '../src/types'
import type { GridNode, GridEdge } from '../src/types'

function makeNode(overrides: Partial<GridNode> = {}): GridNode {
  return {
    id: 'test/bus_1',
    type: 'Bus',
    static: {},
    dynamic: {},
    ...overrides,
  }
}

function makeEdge(overrides: Partial<GridEdge> = {}): GridEdge {
  return {
    id: 'test/line_1',
    type: 'Line',
    source: 'bus_1',
    target: 'bus_2',
    static: {},
    dynamic: {},
    ...overrides,
  }
}

describe('getNodeShortId', () => {
  it('extracts short ID after slash', () => {
    expect(getNodeShortId(makeNode())).toBe('bus_1')
  })
  it('returns full ID if no slash', () => {
    expect(getNodeShortId(makeNode({ id: 'bus_42' }))).toBe('bus_42')
  })
})

describe('getVoltageViolations', () => {
  it('returns 0 for empty nodes', () => {
    expect(getVoltageViolations([])).toBe(0)
  })
  it('detects high voltage', () => {
    const nodes = [makeNode({ dynamic: { vm_pu: VOLTAGE_UPPER_BOUND + 0.01 } })]
    expect(getVoltageViolations(nodes)).toBe(1)
  })
  it('detects low voltage', () => {
    const nodes = [makeNode({ dynamic: { vm_pu: VOLTAGE_LOWER_BOUND - 0.01 } })]
    expect(getVoltageViolations(nodes)).toBe(1)
  })
  it('passes normal voltage', () => {
    const nodes = [makeNode({ dynamic: { vm_pu: 1.0 } })]
    expect(getVoltageViolations(nodes)).toBe(0)
  })
})

describe('getAverageVoltage', () => {
  it('returns 0 for empty', () => {
    expect(getAverageVoltage([])).toBe(0)
  })
  it('computes average', () => {
    const nodes = [
      makeNode({ dynamic: { vm_pu: 1.0 } }),
      makeNode({ dynamic: { vm_pu: 1.02 } }),
    ]
    expect(getAverageVoltage(nodes)).toBeCloseTo(1.01)
  })
})

describe('getMaxLoading', () => {
  it('returns 0 for empty', () => {
    expect(getMaxLoading([])).toBe(0)
  })
  it('finds max loading', () => {
    const edges = [
      makeEdge({ dynamic: { loading_percent: 50 } }),
      makeEdge({ dynamic: { loading_percent: 95 } }),
    ]
    expect(getMaxLoading(edges)).toBe(95)
  })
})

describe('getEdgeStatus', () => {
  it('returns normal for no loading', () => {
    expect(getEdgeStatus(makeEdge())).toBe('normal')
  })
  it('returns critical above threshold', () => {
    expect(getEdgeStatus(makeEdge({ dynamic: { loading_percent: LOADING_CRITICAL + 1 } }))).toBe('critical')
  })
  it('returns warning in warning zone', () => {
    expect(getEdgeStatus(makeEdge({ dynamic: { loading_percent: LOADING_WARNING } }))).toBe('warning')
  })
})

describe('getNodeVoltageStatus', () => {
  it('returns normal for no voltage', () => {
    expect(getNodeVoltageStatus(makeNode())).toBe('normal')
  })
  it('returns low below bound', () => {
    expect(getNodeVoltageStatus(makeNode({ dynamic: { vm_pu: VOLTAGE_LOWER_BOUND - 0.1 } }))).toBe('low')
  })
  it('returns high above bound', () => {
    expect(getNodeVoltageStatus(makeNode({ dynamic: { vm_pu: VOLTAGE_UPPER_BOUND + 0.1 } }))).toBe('high')
  })
  it('returns normal in band', () => {
    expect(getNodeVoltageStatus(makeNode({ dynamic: { vm_pu: 1.0 } }))).toBe('normal')
  })
})
