import { describe, expect, it, vi } from 'vitest'
import type { ChunkSets } from '../chunks/visibility'
import { DEFAULT_SEED, generateWorld } from '../map/generator'
import { toCityMap } from '../map/mapper'
import { chunkKey } from '../map/tiles'
import { CHUNKS_PER_SIDE, type ChunkKey } from '../map/types'
import citizenSystemSrc from './CitizenSystem.ts?raw'
import citizenVisibilitySrc from './citizenVisibility.ts?raw'
import { CitizenSystem } from './CitizenSystem'
import { MASK_SIZE, chunkMask, inMask } from './citizenVisibility'
import mockEngineSrc from './mock/mockEngine.ts?raw'
import travelTimeSrc from './mock/travelTime.ts?raw'
import movementSrc from './MovementSystem.ts?raw'
import { positionAt, type Point } from './MovementSystem'
import { buildRoadGrid } from './roadGrid'
import { samplePolyline, toSidewalk } from './sidewalk'
import { MOCK_TICK_SECONDS } from './SimClock'
import type { MovementEvent } from './types'

const city = toCityMap(generateWorld(DEFAULT_SEED), () => {})
const grid = buildRoadGrid(city)
const TICK_MS = MOCK_TICK_SECONDS * 1000
const ALL: ChunkKey[] = []
for (let x = 0; x < CHUNKS_PER_SIDE; x++) for (let z = 0; z < CHUNKS_PER_SIDE; z++) ALL.push(chunkKey(x, z))
const setsOf = (visible: ChunkKey[], active = visible): ChunkSets => ({ visible: new Set(visible), active: new Set(active), center: [0, 0] })
const allSets = setsOf(ALL)
const make = (count: number, speed: 1 | 4 | 16 = 1) => new CitizenSystem(city, DEFAULT_SEED, count, 0, speed, grid)

// run frames until every visible moving citizen has its path (drain budget spreads it over frames)
function settle(s: CitizenSystem, now: number, sets: ChunkSets) {
  for (let k = 0; k < 400 && (k === 0 || s.perf.pathQueue > 0 || s.perf.pathMisses > 0); k++) s.frame(now, sets)
  s.frame(now, sets)
}

describe('mock formula import boundary (G5)', () => {
  it('render/movement modules do not import the mock travel-time rule', () => {
    for (const src of [movementSrc, citizenVisibilitySrc, citizenSystemSrc]) {
      expect(src).not.toMatch(/travelTime|TILES_PER_TICK|travelTicks/)
    }
    for (const src of [travelTimeSrc, mockEngineSrc]) {
      expect(src.split('\n')[0]).toContain('temporary mock of Python engine rule (docs/02-domain/03-citizen.md §4.4); not permanent frontend domain logic')
    }
  })
})

describe('positionAt (AC3, AC6)', () => {
  const p = toSidewalk(Int32Array.of(0, 1, 2, 514, 1026, 1027)) // synthetic L-shaped tile path
  const e: MovementEvent = { citizenId: 'c', fromBuildingId: 'a', toBuildingId: 'b', startTick: 10, arrivalTick: 14 }
  it('same inputs give the same output; start = path start, arrival = path end; monotonic', () => {
    const a: Point = { x: 0, z: 0, heading: 0 }
    const b: Point = { x: 0, z: 0, heading: 0 }
    positionAt(e, p, 11.3, a)
    positionAt(e, p, 11.3, b)
    expect(a).toEqual(b)
    positionAt(e, p, 10, a)
    expect([a.x, a.z]).toEqual([p.xs[0], p.zs[0]])
    positionAt(e, p, 9, a)
    expect([a.x, a.z]).toEqual([p.xs[0], p.zs[0]])
    positionAt(e, p, 14, a)
    expect([a.x, a.z]).toEqual([p.xs[p.xs.length - 1], p.zs[p.zs.length - 1]])
    // monotonic: each sample equals the polyline point at a non-decreasing arc length
    let prev = -1
    for (let k = 0; k <= 100; k++) {
      const tick = 10 + (4 * k) / 100
      positionAt(e, p, tick, a)
      const s = ((tick - 10) / 4) * p.length
      samplePolyline(p, s, b)
      expect([a.x, a.z]).toEqual([b.x, b.z])
      expect(s).toBeGreaterThanOrEqual(prev)
      prev = s
    }
  })

  it('logical state has no coordinates', () => {
    const s = make(20)
    s.frame(5 * TICK_MS, allSets)
    for (const c of s.store.citizens) for (const k of Object.keys(c)) expect(k).not.toMatch(/^(x|y|z|position|pos)$/i)
    for (const m of s.store.moving) if (m) for (const k of Object.keys(m)) expect(k).not.toMatch(/^(x|y|z|position|pos)$/i)
  })
})

describe('citizenVisibility', () => {
  it('chunkMask / inMask use out[cx*16+cz] with world x/z', () => {
    const m = new Uint8Array(MASK_SIZE)
    chunkMask(new Set<ChunkKey>(['3,5']), m)
    expect(m[3 * 16 + 5]).toBe(1)
    expect(m.reduce((a, b) => a + b, 0)).toBe(1)
    expect(inMask(m, 3 * 32 + 1, 5 * 32 + 31.9)).toBe(true)
    expect(inMask(m, 5 * 32 + 1, 3 * 32 + 1)).toBe(false)
    expect(inMask(m, -1, -1)).toBe(false)
  })
})

describe('CitizenSystem', () => {
  it('sets null -> nothing visible; all chunks visible -> everyone visible', () => {
    const s = make(100)
    s.frame(3 * TICK_MS, null)
    expect(s.visibleCount).toBe(0)
    s.frame(3 * TICK_MS, allSets)
    expect(s.visibleCount).toBe(100)
  })

  it('same seed and clock inputs -> same positions (AC3/AC4)', () => {
    const a = make(300)
    const b = make(300)
    for (const t of [1, 2.5, 7.25, 40.1]) {
      a.frame(t * TICK_MS, allSets)
      b.frame(t * TICK_MS, allSets)
    }
    settle(a, 40.1 * TICK_MS, allSets)
    settle(b, 40.1 * TICK_MS, allSets)
    expect(a.movement.x).toEqual(b.movement.x)
    expect(a.movement.z).toEqual(b.movement.z)
  })

  it('compacts only visible chunks; requests paths only for visible moving citizens', () => {
    const s = make(1000)
    s.frame(20 * TICK_MS, allSets) // pick a busy chunk
    const counts = new Map<ChunkKey, number>()
    for (let i = 0; i < s.total; i++) {
      const k = chunkKey(Math.floor(s.movement.x[i] / 32), Math.floor(s.movement.z[i] / 32))
      counts.set(k, (counts.get(k) ?? 0) + 1)
    }
    const busy = [...counts].sort((a, b) => b[1] - a[1])[0][0]
    const t = make(1000)
    const req = vi.spyOn(t.paths, 'request')
    const vis = setsOf([busy], ALL)
    const mask = new Uint8Array(MASK_SIZE)
    chunkMask(vis.visible, mask)
    let seen = 0
    for (let f = 0; f < 30; f++) {
      t.frame((20 + f * 0.1) * TICK_MS, vis)
      for (const [i] of req.mock.calls.slice(seen)) {
        expect(t.store.moving[i]).not.toBeNull()
        expect(t.slots.subarray(0, t.visibleCount)).toContain(i)
      }
      seen = req.mock.calls.length
      const inSlots = new Set(t.slots.subarray(0, t.visibleCount))
      for (let i = 0; i < t.total; i++) expect(inSlots.has(i)).toBe(inMask(mask, t.movement.x[i], t.movement.z[i]))
    }
    expect(t.visibleCount).toBeGreaterThan(0)
    expect(t.visibleCount).toBeLessThan(t.total)
    expect(req).toHaveBeenCalled()
    expect(new Set(req.mock.calls.map(([i]) => i)).size).toBeLessThan(t.total / 4)
  })

  it('straight-line fallback while path pending, switches to the path once resolved', () => {
    const s = make(1000)
    const now = 30 * TICK_MS
    s.frame(now, allSets)
    const i = s.store.moving.findIndex((m, k) => m && s.movement.approx[k] && m.arrivalTick - m.startTick > 1)
    expect(i).toBeGreaterThanOrEqual(0)
    const e = s.store.moving[i]!
    const tick = s.lastTick
    // fallback: straight lerp between entrance centers with engine timing
    const u = (tick - e.startTick) / (e.arrivalTick - e.startTick)
    const fx = (s.movement.fromTile[i] % 512) + 0.5
    const tx = (s.movement.toTile[i] % 512) + 0.5
    expect(s.movement.x[i]).toBeCloseTo(fx + (tx - fx) * u, 4)
    settle(s, now, allSets)
    expect(s.movement.approx[i]).toBe(0)
    const p = s.movement.polyOf[i]!
    const out: Point = { x: 0, z: 0, heading: 0 }
    positionAt(e, p, tick, out)
    expect(s.movement.x[i]).toBeCloseTo(out.x, 4)
    expect(s.movement.z[i]).toBeCloseTo(out.z, 4)
  })

  it('cancels pending requests when citizens leave visibility', () => {
    const s = make(1000)
    s.frame(30 * TICK_MS, allSets)
    expect(s.paths.stats.queued).toBeGreaterThan(0)
    s.frame(30 * TICK_MS, setsOf([]))
    expect(s.paths.stats.queued).toBe(0)
    expect(s.paths.stats.cancelled).toBeGreaterThan(0)
  })

  it('debug info current matches expectedFresh (fresh engine + fresh path), moving and idle', () => {
    const s = make(300)
    const now = 47.6 * TICK_MS
    s.frame(now, allSets)
    settle(s, now, allSets)
    let movingChecked = 0
    let idleChecked = 0
    for (const c of s.store.citizens) {
      const info = s.info(c.id)!
      const exp = s.expectedFresh(c.id, info.tick)!
      expect(info.slot).not.toBeNull()
      expect(Math.abs(info.current.x - exp.x)).toBeLessThan(1e-3)
      expect(Math.abs(info.current.z - exp.z)).toBeLessThan(1e-3)
      if (info.moving) movingChecked++
      else idleChecked++
    }
    expect(movingChecked).toBeGreaterThan(10)
    expect(idleChecked).toBeGreaterThan(10)
    expect(s.info('nope')).toBeNull()
  })

  it('rebuild = new instance: tick restarts at 0, speed passed in is kept; setSpeed keeps tick continuous', () => {
    const s = make(10, 16)
    expect(s.clock.tickAt(0)).toBe(0)
    expect(s.speed).toBe(16)
    s.frame(TICK_MS, null)
    expect(s.lastTick).toBe(16)
    s.setSpeed(4, TICK_MS)
    s.frame(TICK_MS, null)
    expect(s.lastTick).toBe(16)
  })

  it('benchmark: hidden tab +960 ticks in one frame <= 50 ms, 0 A* in that frame; steady state at 1000', () => {
    const s = make(1000)
    const astar = () => s.paths.stats.misses // each miss = one findPath call
    s.frame(0, null)
    const t0 = performance.now()
    s.frame(960 * TICK_MS, null)
    const catchUp = performance.now() - t0
    expect(astar()).toBe(0)
    console.log(`hidden-tab catch-up 1000 citizens +960 ticks: frame ${catchUp.toFixed(1)} ms (sim ${s.perf.simMs.toFixed(1)} ms, move ${s.perf.moveMs.toFixed(2)} ms)`)
    expect(catchUp).toBeLessThanOrEqual(50)

    // steady state, everything visible (worst case for render work), 60 fps wall time at x16
    let now = 960 * TICK_MS
    for (let f = 0; f < 120; f++) s.frame((now += 16.7 * 16), allSets) // warm-up: resolve paths
    const frames = 600
    let sum = 0
    let sim = 0
    let move = 0
    let path = 0
    for (let f = 0; f < frames; f++) {
      const a = performance.now()
      s.frame((now += 16.7 * 16), allSets)
      sum += performance.now() - a
      sim += s.perf.simMs
      move += s.perf.moveMs
      path += s.perf.pathMs
    }
    const avg = sum / frames
    console.log(
      `steady 1000 citizens all visible x16: avg ${avg.toFixed(3)} ms/frame (sim ${(sim / frames).toFixed(3)}, move ${(move / frames).toFixed(3)}, path ${(path / frames).toFixed(3)}), A* total ${astar()}`,
    )
    expect(avg).toBeLessThan(5)
  })
})
