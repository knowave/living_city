import type { ChunkSets } from '../chunks/visibility'
import type { CityMap } from '../map/types'
import { CitizenStore } from './CitizenStore'
import { MASK_SIZE, chunkMask, inMask } from './citizenVisibility'
import { toCitizen, toMovementEvent } from './mapper'
import { MockEngine, generateCitizens } from './mock/mockEngine'
import { MovementSystem, idlePosition, positionAt, type Point } from './MovementSystem'
import { DRAIN_BUDGET_MS, PathService } from './PathService'
import { findPath } from './pathFinder'
import { buildRoadGrid, entranceTile, type RoadGrid } from './roadGrid'
import { SimClock, type Speed } from './SimClock'
import { straightPolyline, toSidewalk } from './sidewalk'
import { EmploymentStatus, type CitizenDTO, type MovementEvent } from './types'

export interface CitizenDebugInfo {
  moving: boolean
  pathReady: boolean
  approx: boolean // moving and drawn on the straight-line fallback
  tick: number
  slot: number | null
  rendered: { x: number; z: number } | null
  current: { x: number; z: number }
}

export interface CitizenPerf {
  simMs: number // mock engine (server stand-in), measured apart from render work
  moveMs: number // positions, visibility, compaction, path request/cancel
  pathMs: number // PathService.drain
  pathQueue: number
  pathMisses: number // visible moving citizens drawn on the fallback
}

const EMPTY_MASK = new Uint8Array(MASK_SIZE)

// Frame core: no React, no WebGL. Rebuilding (count change) = new instance: tick restarts at 0, pass the current speed.
export class CitizenSystem {
  readonly store: CitizenStore
  readonly movement: MovementSystem
  readonly paths: PathService
  readonly clock: SimClock
  readonly grid: RoadGrid
  readonly slots: Int32Array
  readonly colorIdx: Uint8Array // 0 EMPLOYED, 1 UNEMPLOYED, 2 other
  readonly perf: CitizenPerf = { simMs: 0, moveMs: 0, pathMs: 0, pathQueue: 0, pathMisses: 0 }
  visibleCount = 0
  lastTick = 0

  private readonly city: CityMap
  private readonly seed: number
  private readonly initial: CitizenDTO[]
  private readonly engine: MockEngine
  private readonly requested: Uint8Array // path request queued or resolved for the current trip
  private readonly visMask = new Uint8Array(MASK_SIZE)
  private readonly actMask = new Uint8Array(MASK_SIZE)
  private lastSets: ChunkSets | null = null

  constructor(city: CityMap, seed: number, count: number, nowMs: number, speed: Speed = 1, grid = buildRoadGrid(city)) {
    this.city = city
    this.seed = seed
    this.grid = grid
    this.initial = generateCitizens(city, grid, seed, count)
    const n = this.initial.length
    this.store = new CitizenStore(this.initial.map((d) => toCitizen(d)))
    this.movement = new MovementSystem(city, grid, this.store)
    this.paths = new PathService(grid, city)
    this.paths.onResolved = (i, p) => {
      this.movement.polyOf[i] = p
    }
    this.clock = new SimClock(nowMs, speed)
    this.slots = new Int32Array(n)
    this.requested = new Uint8Array(n)
    this.colorIdx = Uint8Array.from(this.store.citizens, (c) =>
      c.employmentStatus === EmploymentStatus.EMPLOYED ? 0 : c.employmentStatus === EmploymentStatus.UNEMPLOYED ? 1 : 2,
    )
    this.engine = new MockEngine(city, grid, seed, this.initial, {
      movement: (dto) => {
        const e = toMovementEvent(dto)
        const i = e ? this.store.index.get(e.citizenId) : undefined
        if (!e || i === undefined) return
        this.store.applyMovement(e)
        this.movement.invalidate(i)
        this.dropPath(i)
      },
      arrival: (id, buildingId) => {
        const i = this.store.index.get(id)
        if (i === undefined) return
        this.store.applyArrival(id, buildingId)
        this.movement.invalidate(i)
        this.dropPath(i)
      },
    })
  }

  get total(): number {
    return this.store.citizens.length
  }

  get speed(): Speed {
    return this.clock.speed
  }

  setSpeed(speed: Speed, nowMs: number): void {
    this.clock.setSpeed(speed, nowMs)
  }

  // sets null (no view yet / unmounted chunks) -> nothing drawn, pending path requests cancelled
  frame(nowMs: number, sets: ChunkSets | null): void {
    const t0 = performance.now()
    const tick = this.clock.tickAt(nowMs)
    this.lastTick = tick
    this.engine.advanceTo(Math.floor(tick))
    const t1 = performance.now()

    if (sets !== this.lastSets) {
      this.lastSets = sets
      if (sets) {
        chunkMask(sets.visible, this.visMask)
        chunkMask(sets.active, this.actMask)
      }
    }
    const vis = sets ? this.visMask : EMPTY_MASK
    const act = sets ? this.actMask : EMPTY_MASK
    const mv = this.movement
    const moving = this.store.moving
    let count = 0
    let misses = 0
    for (let i = 0; i < this.slots.length; i++) {
      mv.coarse(i, tick)
      // shortcut: a path can stray from the straight line by more than the 1-chunk active ring; such citizens pop in late
      if (inMask(act, mv.x[i], mv.z[i])) mv.refine(i, tick)
      const visible = inMask(vis, mv.x[i], mv.z[i])
      if (visible) {
        this.slots[count++] = i
        if (mv.approx[i]) {
          misses++
          if (!this.requested[i]) {
            const e = moving[i]!
            this.requested[i] = 1
            this.paths.request(i, e.fromBuildingId, e.toBuildingId)
          }
        }
      } else if (this.requested[i] && !mv.polyOf[i]) {
        this.dropPath(i)
      }
    }
    this.visibleCount = count
    const t2 = performance.now()
    this.paths.drain(DRAIN_BUDGET_MS)
    const t3 = performance.now()
    this.perf.simMs = t1 - t0
    this.perf.moveMs = t2 - t1
    this.perf.pathMs = t3 - t2
    this.perf.pathQueue = this.paths.stats.queued
    this.perf.pathMisses = misses
  }

  info(id: string): CitizenDebugInfo | null {
    const i = this.store.index.get(id)
    if (i === undefined) return null
    const mv = this.movement
    mv.place(i, this.lastTick)
    let slot: number | null = null
    for (let k = 0; k < this.visibleCount; k++) if (this.slots[k] === i) slot = k
    const current = { x: mv.x[i], z: mv.z[i] }
    return {
      moving: this.store.moving[i] !== null,
      pathReady: mv.polyOf[i] !== null,
      approx: mv.approx[i] === 1,
      tick: this.lastTick,
      slot,
      rendered: slot === null ? null : current,
      current,
    }
  }

  // Independent expectation: a fresh MockEngine (same seed, this citizen only) advanced to floor(tick) and a fresh A* path.
  expectedFresh(id: string, tick: number): { x: number; z: number } | null {
    const i = this.store.index.get(id)
    if (i === undefined) return null
    let trip: MovementEvent | null = null
    let at = this.initial[i].current_building_id
    const engine = new MockEngine(this.city, this.grid, this.seed, [this.initial[i]], {
      movement: (d) => {
        trip = toMovementEvent(d)
      },
      arrival: (_, b) => {
        trip = null
        at = b
      },
    })
    engine.advanceTo(Math.floor(tick))
    const out: Point = { x: 0, z: 0, heading: 0 }
    const t = trip as MovementEvent | null
    if (t) {
      const from = entranceTile(this.grid, this.city.buildingById.get(t.fromBuildingId)!)
      const to = entranceTile(this.grid, this.city.buildingById.get(t.toBuildingId)!)
      const path = findPath(this.grid, from, to)
      positionAt(t, path ? toSidewalk(path) : straightPolyline(from, to), tick, out)
    } else {
      const b = at ? this.city.buildingById.get(at) : undefined
      if (!b) return null
      idlePosition(this.grid, b, i, out)
    }
    return { x: out.x, z: out.z }
  }

  private dropPath(i: number): void {
    if (!this.requested[i]) return
    this.requested[i] = 0
    this.paths.cancel(i)
  }
}
