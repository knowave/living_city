import { describe, expect, it } from 'vitest'
import { DEFAULT_SEED, generateWorld } from '../../map/generator'
import { toCityMap } from '../../map/mapper'
import { MAP_SIZE } from '../../map/tiles'
import { buildRoadGrid, entranceTile } from '../roadGrid'
import type { MovementEventDTO } from '../types'
import { MockEngine, generateCitizens } from './mockEngine'

const city = toCityMap(generateWorld(DEFAULT_SEED), () => {})
const grid = buildRoadGrid(city)
const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

type Ev = MovementEventDTO | { arrival: string; at: number }

function run(count: number, steps: number[]) {
  const citizens = generateCitizens(city, grid, 7, count)
  const seq = new Map<string, Ev[]>(citizens.map((c) => [c.id, []]))
  let now = 0
  const engine = new MockEngine(city, grid, 7, citizens, {
    movement: (e) => seq.get(e.citizen_id)!.push(e),
    arrival: (id, b) => seq.get(id)!.push({ arrival: b, at: now }),
  })
  for (const t of steps) engine.advanceTo((now = t))
  return seq
}

describe('generateCitizens (AC4)', () => {
  it('is seed-deterministic, valid, and prefix-stable across counts', () => {
    expect(JSON.stringify(generateCitizens(city, grid, 3, 100))).toBe(JSON.stringify(generateCitizens(city, grid, 3, 100)))
    expect(generateCitizens(city, grid, 4, 5)[0].id).not.toBe(generateCitizens(city, grid, 3, 5)[0].id)
    const big = generateCitizens(city, grid, 3, 1000)
    for (const n of [100, 500, 1000]) {
      const list = generateCitizens(city, grid, 3, n)
      expect(list).toHaveLength(n)
      expect(list).toEqual(big.slice(0, n))
      expect(new Set(list.map((c) => c.id)).size).toBe(n)
      for (const c of list) {
        expect(c.id).toMatch(UUID_V4)
        expect(city.buildingById.get(c.home_building_id!)?.type).toBe('RESIDENTIAL')
        expect(c.current_building_id).toBe(c.home_building_id)
        expect(['EMPLOYED', 'UNEMPLOYED']).toContain(c.employment_status)
        expect(c.current_activity).toBe('IDLE')
        expect(c.cash_balance).toBeNull()
      }
    }
  })
})

describe('MockEngine (AC4)', () => {
  it('per-citizen event sequences: 1-tick stepping == one jump; 100 run == first 100 of 1000', () => {
    const stepped = run(100, Array.from({ length: 201 }, (_, t) => t))
    const jumped = run(100, [200])
    const thousand = run(1000, [200])
    let events = 0
    for (const [id, evs] of stepped) {
      const strip = (l: Ev[]) => l.map((e) => ('arrival' in e ? e.arrival : e))
      expect(strip(jumped.get(id)!)).toEqual(strip(evs))
      expect(strip(thousand.get(id)!)).toEqual(strip(evs))
      events += evs.length
    }
    expect(events).toBeGreaterThan(1000)
  })

  it('trips chain: start >= 1, arrival - start = max(1, ceil(manhattan(entrances)/40)), same component, within ±2 chunks', () => {
    const N = MAP_SIZE
    for (const evs of run(200, [300]).values()) {
      let at = -1
      let prevTo: string | null = null
      for (const e of evs) {
        if ('arrival' in e) continue
        const a = city.buildingById.get(e.from_building_id)!
        const b = city.buildingById.get(e.to_building_id)!
        const fa = entranceTile(grid, a)
        const fb = entranceTile(grid, b)
        const manhattan = Math.abs((fa % N) - (fb % N)) + Math.abs(Math.floor(fa / N) - Math.floor(fb / N))
        expect(e.arrival_tick - e.start_tick).toBe(Math.max(1, Math.ceil(manhattan / 40)))
        expect(e.start_tick).toBeGreaterThanOrEqual(Math.max(1, at + 1))
        if (prevTo) expect(e.from_building_id).toBe(prevTo)
        expect(grid.component[fb]).toBe(grid.component[fa])
        expect(Math.abs(Math.floor(a.tileX / 32) - Math.floor(b.tileX / 32))).toBeLessThanOrEqual(2)
        expect(Math.abs(Math.floor(a.tileY / 32) - Math.floor(b.tileY / 32))).toBeLessThanOrEqual(2)
        expect(e.from_building_id).not.toBe(e.to_building_id)
        at = e.arrival_tick
        prevTo = e.to_building_id
      }
    }
  })
})
