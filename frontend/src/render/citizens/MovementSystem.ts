import { MAP_SIZE } from '../map/tiles'
import type { Building, CityMap } from '../map/types'
import type { CitizenStore } from './CitizenStore'
import { entranceTile, type RoadGrid } from './roadGrid'
import { SIDEWALK_OFFSET, samplePolyline, type Polyline } from './sidewalk'
import type { MovementEvent } from './types'

export const CITIZEN_Y = 0.05 // above road 0.02 / markings 0.04 (chunks/groundGeometry.ts)
const IDLE_JITTER = 0.18
const N = MAP_SIZE

export interface Point {
  x: number
  z: number
  heading: number
}

// Rendering of ticks given by the engine: no travel-time rule here, only start/arrival interpolation.
export function progress(e: MovementEvent, tick: number): number {
  return Math.min(Math.max((tick - e.startTick) / (e.arrivalTick - e.startTick), 0), 1)
}

export function positionAt(e: MovementEvent, p: Polyline, tick: number, out: Point): void {
  samplePolyline(p, progress(e, tick) * p.length, out)
}

// straight line between entrance tile centers, same timing (path not resolved yet)
export function straightAt(fromTile: number, toTile: number, u: number, out: Point): void {
  const fx = (fromTile % N) + 0.5
  const fz = Math.floor(fromTile / N) + 0.5
  const dx = (toTile % N) + 0.5 - fx
  const dz = Math.floor(toTile / N) + 0.5 - fz
  out.x = fx + dx * u
  out.z = fz + dz * u
  if (dx || dz) out.heading = Math.atan2(dx, dz)
}

// beside the entrance road tile, pushed toward the building, jittered along the building edge
export function idlePosition(grid: RoadGrid, b: Building, citizenIndex: number, out: Point): void {
  const ent = entranceTile(grid, b)
  if (ent < 0) {
    out.x = b.tileX + b.width / 2
    out.z = b.tileY + b.height / 2
    out.heading = 0
    return
  }
  const ex = (ent % N) + 0.5
  const ez = Math.floor(ent / N) + 0.5
  const tx = Math.min(Math.max(ex, b.tileX + 0.5), b.tileX + b.width - 0.5) - ex
  const tz = Math.min(Math.max(ez, b.tileY + 0.5), b.tileY + b.height - 0.5) - ez
  const l = Math.hypot(tx, tz) || 1
  const nx = tx / l
  const nz = tz / l
  const j = ((((citizenIndex + 1) * 2654435761) >>> 0) % 1000 / 999 - 0.5) * 2 * IDLE_JITTER
  out.x = ex + nx * SIDEWALK_OFFSET - nz * j
  out.z = ez + nz * SIDEWALK_OFFSET + nx * j
  out.heading = Math.atan2(-nx, -nz) // facing the road
}

const tmp: Point = { x: 0, z: 0, heading: 0 }

// SoA render state. Positions are recomputed from (store event, tick, polyline); never stored in the store.
export class MovementSystem {
  readonly x: Float32Array
  readonly z: Float32Array
  readonly heading: Float32Array
  readonly approx: Uint8Array // 1 = moving, drawn on the straight-line fallback
  readonly polyOf: (Polyline | null)[]
  readonly fromTile: Int32Array
  readonly toTile: Int32Array
  readonly idleX: Float32Array
  readonly idleZ: Float32Array
  readonly idleH: Float32Array
  readonly stale: Uint8Array // 1 = logical state changed since last coarse(); recompute tiles / idle spot lazily
  private readonly city: CityMap
  private readonly grid: RoadGrid
  private readonly store: CitizenStore

  constructor(city: CityMap, grid: RoadGrid, store: CitizenStore) {
    const n = store.citizens.length
    this.city = city
    this.grid = grid
    this.store = store
    this.x = new Float32Array(n)
    this.z = new Float32Array(n)
    this.heading = new Float32Array(n)
    this.approx = new Uint8Array(n)
    this.polyOf = new Array<Polyline | null>(n).fill(null)
    this.fromTile = new Int32Array(n).fill(-1)
    this.toTile = new Int32Array(n).fill(-1)
    this.idleX = new Float32Array(n).fill(-1)
    this.idleZ = new Float32Array(n).fill(-1)
    this.idleH = new Float32Array(n)
    this.stale = new Uint8Array(n).fill(1)
  }

  // trip changed (movement or arrival): the old path no longer applies; tiles / idle spot are rebuilt on next coarse()
  invalidate(i: number): void {
    this.polyOf[i] = null
    this.stale[i] = 1
  }

  private begin(i: number, e: MovementEvent): void {
    const a = this.city.buildingById.get(e.fromBuildingId)
    const b = this.city.buildingById.get(e.toBuildingId)
    this.fromTile[i] = a ? entranceTile(this.grid, a) : -1
    this.toTile[i] = b ? entranceTile(this.grid, b) : -1
  }

  private settle(i: number, buildingId: string | null): void {
    const b = buildingId ? this.city.buildingById.get(buildingId) : undefined
    if (!b) return // stays at (-1,-1): outside every chunk, never drawn
    idlePosition(this.grid, b, i, tmp)
    this.idleX[i] = tmp.x
    this.idleZ[i] = tmp.z
    this.idleH[i] = tmp.heading
  }

  // coarse position only (idle spot or straight line); cheap visibility pre-check
  coarse(i: number, tick: number): void {
    const e = this.store.moving[i]
    if (this.stale[i]) {
      this.stale[i] = 0
      if (e) this.begin(i, e)
      else this.settle(i, this.store.citizens[i].currentBuildingId)
    }
    if (!e || this.fromTile[i] < 0 || this.toTile[i] < 0) {
      this.x[i] = this.idleX[i]
      this.z[i] = this.idleZ[i]
      this.heading[i] = this.idleH[i]
      this.approx[i] = 0
      return
    }
    tmp.heading = this.heading[i]
    straightAt(this.fromTile[i], this.toTile[i], progress(e, tick), tmp)
    this.x[i] = tmp.x
    this.z[i] = tmp.z
    this.heading[i] = tmp.heading
    this.approx[i] = 1
  }

  // exact render position: path if resolved, else the straight-line fallback
  place(i: number, tick: number): void {
    this.coarse(i, tick)
    this.refine(i, tick)
  }

  // after coarse(): switch a moving citizen to its resolved path
  refine(i: number, tick: number): void {
    const e = this.store.moving[i]
    const p = this.polyOf[i]
    if (!e || !p) return
    tmp.heading = this.heading[i]
    positionAt(e, p, tick, tmp)
    this.x[i] = tmp.x
    this.z[i] = tmp.z
    this.heading[i] = tmp.heading
    this.approx[i] = 0
  }
}
