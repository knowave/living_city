// temporary mock of Python engine rule (docs/02-domain/03-citizen.md §4.4); not permanent frontend domain logic.
// Stands in for the server: outputs only DTOs through EngineSink (the SSE replacement point). No A*.
import { mulberry32, uuidV4 } from '../../map/prng'
import { worldToChunk } from '../../map/tiles'
import { CHUNKS_PER_SIDE, type Building, type CityMap } from '../../map/types'
import { entranceTile, type RoadGrid } from '../roadGrid'
import { CitizenActivity, EmploymentStatus, type CitizenDTO, type MovementEventDTO } from '../types'
import { travelTicks } from './travelTime'

const DEST_CHUNK_RADIUS = 2
const DEST_TRIES = 8
const DWELL_MIN = 1
const DWELL_MAX = 6
const SYLLABLES = ['min', 'seo', 'ji', 'ha', 'yun', 'do', 'hyun', 'soo', 'eun', 'jae', 'woo', 'na', 'ra', 'bin', 'kyu', 'tae']

const randInt = (rng: () => number, min: number, max: number) => min + Math.floor(rng() * (max - min + 1))

// per-citizen stream: independent of processing order, so count=100 equals the first 100 of count=1000
function citizenRng(seed: number, i: number): () => number {
  return mulberry32(Math.imul(seed ^ 0x9e3779b9, 0x85ebca6b) ^ Math.imul(i + 1, 0xc2b2ae35))
}

// engine stream keyed by citizen id, so a single citizen can be re-simulated alone (expectedFresh)
function engineRng(seed: number, id: string): () => number {
  let h = (0x811c9dc5 ^ seed) >>> 0
  for (let k = 0; k < id.length; k++) h = Math.imul(h ^ id.charCodeAt(k), 0x01000193)
  return mulberry32(h)
}

// buildings with an entrance on the main road component (generator guarantees all of them)
function reachable(city: CityMap, grid: RoadGrid): Building[] {
  return [...city.buildingById.values()].filter((b) => {
    const e = entranceTile(grid, b)
    return e >= 0 && grid.component[e] === grid.main
  })
}

export function generateCitizens(city: CityMap, grid: RoadGrid, seed: number, count: number): CitizenDTO[] {
  const all = reachable(city, grid)
  const homes = all.filter((b) => b.type === 'RESIDENTIAL')
  const pool = homes.length ? homes : all
  const out: CitizenDTO[] = []
  for (let i = 0; i < count && pool.length; i++) {
    const rng = citizenRng(seed, i)
    const id = uuidV4(rng)
    const home = pool[Math.floor(rng() * pool.length)].id
    const sy = () => SYLLABLES[Math.floor(rng() * SYLLABLES.length)]
    const name = `${sy()}${sy()} ${sy()}`
    out.push({
      id,
      world_id: city.worldId,
      household_id: null,
      name,
      age: randInt(rng, 18, 80),
      home_building_id: home,
      current_building_id: home,
      employment_status: rng() < 0.8 ? EmploymentStatus.EMPLOYED : EmploymentStatus.UNEMPLOYED,
      employer_id: null,
      happiness: randInt(rng, 50, 100),
      health: randInt(rng, 50, 100),
      skills: {},
      risk_tolerance: rng(),
      consumption_preference: rng(),
      current_activity: CitizenActivity.IDLE,
      current_destination: null,
      arrival_tick: null,
      cash_balance: null,
    })
  }
  return out
}

export interface EngineSink {
  movement(e: MovementEventDTO): void
  arrival(citizenId: string, buildingId: string): void
}

export class MockEngine {
  private readonly ids: string[]
  private readonly rngs: (() => number)[]
  private readonly buildings: Building[]
  private readonly entrance: Int32Array
  private readonly candidates: Int32Array[] // by anchor chunk cx*16+cy: buildings within ±2 chunks
  private readonly chunkOf: Int32Array
  private readonly cur: Int32Array
  private readonly dest: Int32Array
  private readonly arrivalAt: Int32Array // -1 = idle
  private readonly next: Int32Array // next departure tick while idle
  private readonly sink: EngineSink

  constructor(city: CityMap, grid: RoadGrid, seed: number, initial: CitizenDTO[], sink: EngineSink) {
    this.sink = sink
    this.buildings = reachable(city, grid)
    const index = new Map(this.buildings.map((b, k) => [b.id, k]))
    this.entrance = Int32Array.from(this.buildings, (b) => entranceTile(grid, b))
    this.chunkOf = Int32Array.from(this.buildings, (b) => {
      const { chunkX, chunkY } = worldToChunk(b.tileX, b.tileY)
      return chunkX * CHUNKS_PER_SIDE + chunkY
    })
    const byChunk: number[][] = Array.from({ length: CHUNKS_PER_SIDE * CHUNKS_PER_SIDE }, () => [])
    this.chunkOf.forEach((c, k) => byChunk[c].push(k))
    this.candidates = byChunk.map((_, c) => {
      const cx = Math.floor(c / CHUNKS_PER_SIDE)
      const cy = c % CHUNKS_PER_SIDE
      const list: number[] = []
      for (let x = cx - DEST_CHUNK_RADIUS; x <= cx + DEST_CHUNK_RADIUS; x++)
        for (let y = cy - DEST_CHUNK_RADIUS; y <= cy + DEST_CHUNK_RADIUS; y++)
          if (x >= 0 && y >= 0 && x < CHUNKS_PER_SIDE && y < CHUNKS_PER_SIDE) list.push(...byChunk[x * CHUNKS_PER_SIDE + y])
      return Int32Array.from(list)
    })
    const n = initial.length
    this.ids = initial.map((c) => c.id)
    this.rngs = initial.map((c) => engineRng(seed, c.id))
    this.cur = Int32Array.from(initial, (c) => index.get(c.current_building_id ?? '') ?? -1)
    this.dest = new Int32Array(n).fill(-1)
    this.arrivalAt = new Int32Array(n).fill(-1)
    // shortcut: initial DTOs are assumed IDLE (generateCitizens only makes IDLE); accept MOVING when SSE snapshots arrive
    this.next = Int32Array.from(this.rngs, (rng, i) => (this.cur[i] < 0 ? 0x7fffffff : randInt(rng, DWELL_MIN, DWELL_MAX)))
  }

  // integer, monotonic. O(due trips) arithmetic per citizen.
  advanceTo(tick: number): void {
    for (let i = 0; i < this.ids.length; i++) {
      for (;;) {
        const arrival = this.arrivalAt[i]
        if (arrival >= 0) {
          if (arrival > tick) break
          this.cur[i] = this.dest[i]
          this.arrivalAt[i] = -1
          this.next[i] = arrival + randInt(this.rngs[i], DWELL_MIN, DWELL_MAX)
          this.sink.arrival(this.ids[i], this.buildings[this.cur[i]].id)
        } else {
          if (this.next[i] > tick) break
          this.depart(i)
        }
      }
    }
  }

  private depart(i: number): void {
    const rng = this.rngs[i]
    const from = this.cur[i]
    const cands = this.candidates[this.chunkOf[from]]
    let to = -1
    for (let k = 0; k < DEST_TRIES && to < 0; k++) {
      const c = cands[Math.floor(rng() * cands.length)]
      if (c !== from) to = c
    }
    if (to < 0) {
      this.next[i] += randInt(rng, DWELL_MIN, DWELL_MAX)
      return
    }
    const start = this.next[i] // scheduled tick, not the processing tick
    const arrival = start + travelTicks(this.entrance[from], this.entrance[to])
    this.dest[i] = to
    this.arrivalAt[i] = arrival
    this.sink.movement({
      citizen_id: this.ids[i],
      from_building_id: this.buildings[from].id,
      to_building_id: this.buildings[to].id,
      start_tick: start,
      arrival_tick: arrival,
    })
  }
}
