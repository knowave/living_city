import { CHUNK_SIZE, type Building, type CityMap } from '../map/types'
import { MAP_SIZE, decodeRoad } from '../map/tiles'

export interface RoadGrid {
  conn: Uint8Array // N|E|S|W bits (1,2,4,8) of walkable edges per tile; 0 = no edge
  component: Int32Array // connected component id, -1 = not road
  main: number // id of the largest component
  entrances: Map<string, number> // entranceTile cache by building id
}

const N = MAP_SIZE
const DX = [0, 1, 0, -1] // N E S W, matches Dir bits 1,2,4,8
const DY = [-1, 0, 1, 0]

export function buildRoadGrid(city: CityMap): RoadGrid {
  const conn = new Uint8Array(N * N)
  const component = new Int32Array(N * N).fill(-2) // -2 = unvisited road, -1 = not road
  for (const c of city.chunks.values())
    for (let i = 0; i < c.roadTiles.length; i++) {
      const g = (c.chunkY * CHUNK_SIZE + Math.floor(i / CHUNK_SIZE)) * N + c.chunkX * CHUNK_SIZE + (i % CHUNK_SIZE)
      const d = decodeRoad(c.roadTiles[i])
      component[g] = d ? -2 : -1
      conn[g] = d ? d.connection & 15 : 0 // ROAD_ISOLATED (16) has no edges
    }
  let main = -1
  let mainSize = 0
  let id = 0
  const stack = new Int32Array(N * N)
  for (let s = 0; s < N * N; s++) {
    if (component[s] !== -2) continue
    let sp = 0
    let size = 0
    stack[sp++] = s
    component[s] = id
    while (sp) {
      const t = stack[--sp]
      size++
      for (let k = 0; k < 4; k++) {
        if (!(conn[t] & (1 << k))) continue
        const n = t + DY[k] * N + DX[k]
        if (component[n] === -2) {
          component[n] = id
          stack[sp++] = n
        }
      }
    }
    if (size > mainSize) {
      mainSize = size
      main = id
    }
    id++
  }
  return { conn, component, main, entrances: new Map() }
}

// first road tile around the footprint: top row, right col, bottom row, left col (each ascending)
export function entranceTile(grid: RoadGrid, b: Building): number {
  const hit = grid.entrances.get(b.id)
  if (hit !== undefined) return hit
  const { tileX: x, tileY: y, width: w, height: h } = b
  const at = (tx: number, ty: number) => (tx >= 0 && ty >= 0 && tx < N && ty < N && grid.component[ty * N + tx] >= 0 ? ty * N + tx : -1)
  let r = -1
  for (let k = 0; k < w && r < 0; k++) r = at(x + k, y - 1)
  for (let k = 0; k < h && r < 0; k++) r = at(x + w, y + k)
  for (let k = 0; k < w && r < 0; k++) r = at(x + k, y + h)
  for (let k = 0; k < h && r < 0; k++) r = at(x - 1, y + k)
  grid.entrances.set(b.id, r)
  return r
}
