import { MAP_SIZE } from '../map/tiles'

export interface Polyline {
  xs: Float32Array
  zs: Float32Array
  cum: Float32Array // cumulative length at each point
  length: number
}

const N = MAP_SIZE
export const SIDEWALK_OFFSET = 0.35

function build(px: number[], pz: number[]): Polyline {
  const xs = Float32Array.from(px)
  const zs = Float32Array.from(pz)
  const cum = new Float32Array(xs.length)
  for (let i = 1; i < xs.length; i++) cum[i] = cum[i - 1] + Math.hypot(xs[i] - xs[i - 1], zs[i] - zs[i - 1])
  return { xs, zs, cum, length: cum[cum.length - 1] }
}

// Tile centers are (x+0.5, y+0.5), world +z = tile +y. Right of travel (dx,dz) is (-dz, dx).
export function toSidewalk(path: Int32Array, offset = SIDEWALK_OFFSET): Polyline {
  // keep only start, corners and end
  const px: number[] = []
  const pz: number[] = []
  const dirs: number[][] = [] // direction leaving each kept point (last: arriving)
  for (let i = 0; i < path.length; i++) {
    const x = (path[i] % N) + 0.5
    const z = Math.floor(path[i] / N) + 0.5
    let d: number[] | null = null
    if (i > 0) d = [x - (path[i - 1] % N) - 0.5, z - Math.floor(path[i - 1] / N) - 0.5]
    if (i > 0 && i < path.length - 1) {
      const nx = (path[i + 1] % N) + 0.5 - x
      const nz = Math.floor(path[i + 1] / N) + 0.5 - z
      if (d![0] === nx && d![1] === nz) continue
    }
    px.push(x)
    pz.push(z)
    dirs.push(d ?? [0, 0])
  }
  if (px.length === 1) return build(px, pz)
  // d_in / d_out per kept point
  const last = px.length - 1
  for (let i = 0; i <= last; i++) {
    const din = i === 0 ? dirs[1] : dirs[i]
    const dout = i === last ? dirs[last] : dirs[i + 1]
    const n1 = unitRight(din)
    const n2 = unitRight(dout)
    const k = offset / (1 + n1[0] * n2[0] + n1[1] * n2[1])
    px[i] += (n1[0] + n2[0]) * k
    pz[i] += (n1[1] + n2[1]) * k
  }
  return build(px, pz)
}

function unitRight(d: number[]): [number, number] {
  const l = Math.hypot(d[0], d[1])
  return [-d[1] / l, d[0] / l]
}

// not-ready fallback: straight line between two entrance tiles, no offset
export function straightPolyline(fromTile: number, toTile: number): Polyline {
  return build(
    [(fromTile % N) + 0.5, (toTile % N) + 0.5],
    [Math.floor(fromTile / N) + 0.5, Math.floor(toTile / N) + 0.5],
  )
}

// heading = atan2(dx, dz): yaw about +Y, 0 faces +z
export function samplePolyline(p: Polyline, s: number, out: { x: number; z: number; heading: number }): void {
  const n = p.xs.length
  if (n === 1) {
    out.x = p.xs[0]
    out.z = p.zs[0]
    return
  }
  let lo = 1
  let hi = n - 1
  const t = Math.min(Math.max(s, 0), p.length)
  while (lo < hi) {
    const m = (lo + hi) >> 1
    if (p.cum[m] < t) lo = m + 1
    else hi = m
  }
  const seg = p.cum[lo] - p.cum[lo - 1]
  const f = seg > 0 ? (t - p.cum[lo - 1]) / seg : 0
  out.x = p.xs[lo - 1] + (p.xs[lo] - p.xs[lo - 1]) * f
  out.z = p.zs[lo - 1] + (p.zs[lo] - p.zs[lo - 1]) * f
  out.heading = Math.atan2(p.xs[lo] - p.xs[lo - 1], p.zs[lo] - p.zs[lo - 1])
}
