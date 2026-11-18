import { describe, expect, it } from 'vitest'
import { createFpsTracker, type FpsStats } from './fps'

describe('createFpsTracker', () => {
  it('reports ~60 fps for 60 ticks per second', () => {
    const tracker = createFpsTracker()
    let last: FpsStats | null = null
    for (let i = 0; i <= 120; i++) {
      const stats = tracker.tick(i / 60)
      if (stats) last = stats
    }
    expect(last).not.toBeNull()
    expect(last!.fps).toBeCloseTo(60, 0)
    expect(last!.avg).toBeCloseTo(60, 0)
  })

  it('returns null between reports and a value at each 0.5s boundary', () => {
    const tracker = createFpsTracker()
    const results: (FpsStats | null)[] = []
    for (let i = 0; i <= 60; i++) results.push(tracker.tick(i / 60))
    const reported = results.map((r, i) => (r ? i : -1)).filter((i) => i >= 0)
    expect(reported).toEqual([30, 60])
    expect(results[1]).toBeNull()
    expect(results[29]).toBeNull()
  })
})
