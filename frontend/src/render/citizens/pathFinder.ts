import { MAP_SIZE } from '../map/tiles'
import type { RoadGrid } from './roadGrid'

const N = MAP_SIZE
const MAX_EXPANDED = 20000
const HEAP_CAP = 1 << 17 // lazy-deletion pushes <= 4 per expansion
const DX = [0, 1, 0, -1]
const DY = [-1, 0, 1, 0]

// scratch buffers: findPath is synchronous and non-reentrant
const g = new Int32Array(N * N)
const came = new Int32Array(N * N)
const seen = new Uint32Array(N * N) // generation stamp: g/came valid
const closed = new Uint32Array(N * N)
const heapNode = new Int32Array(HEAP_CAP)
const heapKey = new Int32Array(HEAP_CAP) // f * 4096 + h
let gen = 0

// A*, uniform cost 1, Manhattan heuristic. Tile index = y*512+x. Returns from..to inclusive, or null.
export function findPath(grid: RoadGrid, from: number, to: number): Int32Array | null {
  if (grid.component[from] < 0 || grid.component[from] !== grid.component[to]) return null
  if (from === to) return Int32Array.of(from)
  if (++gen === 0xffffffff) {
    seen.fill(0)
    closed.fill(0)
    gen = 1
  }
  const tx = to % N
  const ty = (to / N) | 0
  const h = (t: number) => Math.abs((t % N) - tx) + Math.abs(((t / N) | 0) - ty)
  let size = 0
  const push = (node: number, key: number) => {
    let i = size++
    while (i > 0) {
      const p = (i - 1) >> 1
      if (heapKey[p] < key || (heapKey[p] === key && heapNode[p] <= node)) break
      heapKey[i] = heapKey[p]
      heapNode[i] = heapNode[p]
      i = p
    }
    heapKey[i] = key
    heapNode[i] = node
  }
  const pop = () => {
    const top = heapNode[0]
    const key = heapKey[--size]
    const node = heapNode[size]
    let i = 0
    for (;;) {
      let c = 2 * i + 1
      if (c >= size) break
      if (c + 1 < size && (heapKey[c + 1] < heapKey[c] || (heapKey[c + 1] === heapKey[c] && heapNode[c + 1] < heapNode[c]))) c++
      if (heapKey[c] > key || (heapKey[c] === key && heapNode[c] >= node)) break
      heapKey[i] = heapKey[c]
      heapNode[i] = heapNode[c]
      i = c
    }
    heapKey[i] = key
    heapNode[i] = node
    return top
  }

  g[from] = 0
  came[from] = -1
  seen[from] = gen
  const h0 = h(from)
  push(from, h0 * 4096 + h0)
  let expanded = 0
  while (size > 0) {
    const t = pop()
    if (closed[t] === gen) continue
    closed[t] = gen
    if (t === to) {
      const path = new Int32Array(g[t] + 1)
      for (let n = t, i = g[t]; n >= 0; n = came[n], i--) path[i] = n
      return path
    }
    if (++expanded > MAX_EXPANDED) return null
    const c = grid.conn[t]
    for (let k = 0; k < 4; k++) {
      if (!(c & (1 << k))) continue
      const n = t + DY[k] * N + DX[k]
      const ng = g[t] + 1
      if (closed[n] === gen || (seen[n] === gen && g[n] <= ng)) continue
      if (size >= HEAP_CAP) return null
      seen[n] = gen
      g[n] = ng
      came[n] = t
      const hn = h(n)
      push(n, (ng + hn) * 4096 + hn)
    }
  }
  return null
}
