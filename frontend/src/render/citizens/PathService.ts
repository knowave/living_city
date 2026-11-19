import type { CityMap } from '../map/types'
import { findPath } from './pathFinder'
import { entranceTile, type RoadGrid } from './roadGrid'
import { toSidewalk, type Polyline } from './sidewalk'

export const PATH_CACHE_MAX = 2048
export const DRAIN_BUDGET_MS = 1
export const DRAIN_MAX_COUNT = 64

interface Req {
  key: number
  from: number
  to: number
}

// Per-frame path scheduler. Call request/cancel/drain outside the per-citizen position loop.
export class PathService {
  onResolved: (citizen: number, p: Polyline | null) => void = () => {}
  readonly stats = { cacheSize: 0, queued: 0, resolved: 0, cacheHits: 0, cancelled: 0, misses: 0 }
  private pending = new Map<number, Req>() // insertion order = FIFO
  private last = new Map<number, number>() // citizen -> key of its queued/resolved request
  private cache = new Map<number, Polyline | null>() // Map order = LRU; null = unreachable

  private grid: RoadGrid
  private city: CityMap
  private max: number

  constructor(grid: RoadGrid, city: CityMap, max = PATH_CACHE_MAX) {
    this.grid = grid
    this.city = city
    this.max = max
  }

  request(citizen: number, fromId: string, toId: string): void {
    const a = this.city.buildingById.get(fromId)
    const b = this.city.buildingById.get(toId)
    const from = a ? entranceTile(this.grid, a) : -1
    const to = b ? entranceTile(this.grid, b) : -1
    if (from < 0 || to < 0) {
      this.cancel(citizen)
      this.onResolved(citizen, null)
      return
    }
    const key = from * 262144 + to
    if (this.last.get(citizen) === key) return
    this.pending.delete(citizen)
    this.last.set(citizen, key)
    if (this.cache.has(key)) {
      this.stats.cacheHits++
      this.finish(citizen, this.touch(key))
      return
    }
    this.pending.set(citizen, { key, from, to })
    this.stats.queued = this.pending.size
  }

  cancel(citizen: number): void {
    if (this.pending.delete(citizen)) this.stats.cancelled++
    this.last.delete(citizen)
    this.stats.queued = this.pending.size
  }

  // processes at least one request, stops at budgetMs or maxCount; returns count processed
  drain(budgetMs = DRAIN_BUDGET_MS, now: () => number = () => performance.now(), maxCount = DRAIN_MAX_COUNT): number {
    const t0 = now()
    let n = 0
    for (const [citizen, r] of this.pending) {
      if (n > 0 && (n >= maxCount || now() - t0 >= budgetMs)) break
      this.pending.delete(citizen)
      let p: Polyline | null
      if (this.cache.has(r.key)) {
        this.stats.cacheHits++
        p = this.touch(r.key)
      } else {
        this.stats.misses++
        const path = findPath(this.grid, r.from, r.to)
        p = path ? toSidewalk(path) : null
        this.cache.set(r.key, p)
        if (this.cache.size > this.max) this.cache.delete(this.cache.keys().next().value!)
        this.stats.cacheSize = this.cache.size
      }
      this.finish(citizen, p)
      n++
    }
    this.stats.queued = this.pending.size
    return n
  }

  private touch(key: number): Polyline | null {
    const p = this.cache.get(key)!
    this.cache.delete(key)
    this.cache.set(key, p)
    return p
  }

  private finish(citizen: number, p: Polyline | null): void {
    this.stats.resolved++
    this.onResolved(citizen, p)
  }
}
