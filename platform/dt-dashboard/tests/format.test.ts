import { describe, it, expect } from 'vitest'
import { formatTimestamp, formatCount, formatPercent, formatPu, timeAgo } from '../src/utils/format'

describe('formatTimestamp', () => {
  it('formats ISO string', () => {
    const result = formatTimestamp('2026-06-22T10:30:00Z')
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })
  it('returns -- for null', () => {
    expect(formatTimestamp(null)).toBe('--')
  })
  it('returns -- for undefined', () => {
    expect(formatTimestamp(undefined)).toBe('--')
  })
})

describe('formatCount', () => {
  it('formats small numbers', () => {
    expect(formatCount(42)).toBe('42')
  })
  it('formats thousands', () => {
    expect(formatCount(1500)).toBe('1.5K')
  })
  it('formats millions', () => {
    expect(formatCount(2_500_000)).toBe('2.5M')
  })
})

describe('formatPercent', () => {
  it('formats with default decimals', () => {
    expect(formatPercent(95.678)).toBe('95.7%')
  })
  it('formats with custom decimals', () => {
    expect(formatPercent(95.678, 2)).toBe('95.68%')
  })
})

describe('formatPu', () => {
  it('formats with 4 decimals', () => {
    expect(formatPu(1.01234)).toBe('1.0123')
  })
})

describe('timeAgo', () => {
  it('returns just now for recent', () => {
    expect(timeAgo(Date.now() - 1000)).toBe('just now')
  })
  it('returns seconds', () => {
    expect(timeAgo(Date.now() - 10000)).toBe('10s ago')
  })
  it('returns minutes', () => {
    expect(timeAgo(Date.now() - 120000)).toBe('2m ago')
  })
  it('returns never for null', () => {
    expect(timeAgo(null)).toBe('never')
  })
})
