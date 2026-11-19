import { describe, expect, it } from 'vitest'
import { MOCK_TICK_SECONDS, SimClock } from './SimClock'

const MS = MOCK_TICK_SECONDS * 1000

describe('SimClock', () => {
  it('derives fractional tick from injected time', () => {
    const c = new SimClock(1000)
    expect(c.tickAt(1000)).toBe(0)
    expect(c.tickAt(1000 + MS / 2)).toBeCloseTo(0.5)
    expect(c.tickAt(1000 + 3 * MS)).toBeCloseTo(3)
  })
  it('scales by speed', () => {
    expect(new SimClock(0, 16).tickAt(MS)).toBeCloseTo(16)
  })
  it('keeps tick continuous when speed changes', () => {
    const c = new SimClock(0)
    const before = c.tickAt(2 * MS)
    c.setSpeed(4, 2 * MS)
    expect(c.tickAt(2 * MS)).toBeCloseTo(before)
    expect(c.tickAt(3 * MS)).toBeCloseTo(before + 4)
    expect(c.speed).toBe(4)
  })
})
