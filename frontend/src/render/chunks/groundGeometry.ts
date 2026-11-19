import * as THREE from 'three'
import { CHUNK_SIZE, type Chunk } from '../map/types'
import { Dir, RoadClass, ROAD_ISOLATED, Terrain, tileIndex } from '../map/tiles'

const Y_TERRAIN = 0
const Y_ROAD = 0.02
const Y_MARK = 0.04

const TERRAIN_COLOR = ['#5f9e4f', '#3a7bc8', '#e3d49b']
const ROAD_COLOR = ['#55585e', '#33363b']
const MARK_COLOR = ['#d0d0d0', '#f2d14b']

const colorCache = new Map<string, [number, number, number]>()
// new Color(hex) converts sRGB hex to linear working space
function rgb(hex: string): [number, number, number] {
  let c = colorCache.get(hex)
  if (!c) {
    const col = new THREE.Color(hex)
    c = [col.r, col.g, col.b]
    colorCache.set(hex, c)
  }
  return c
}

// Marks as [x0, z0, x1, z1] offsets inside the tile; N = -z, S = +z.
const MARKS: [number, [number, number, number, number]][] = [
  [Dir.N, [0.46, 0, 0.54, 0.5]],
  [Dir.E, [0.5, 0.46, 1, 0.54]],
  [Dir.S, [0.46, 0.5, 0.54, 1]],
  [Dir.W, [0, 0.46, 0.5, 0.54]],
]

export function buildGroundBuffers(chunk: Chunk) {
  // upper bound: 1024 terrain + 1024 * (full road tile + 4 marks) quads
  const maxQuads = 1024 * 6
  const position = new Float32Array(maxQuads * 12)
  const normal = new Float32Array(maxQuads * 12)
  const color = new Float32Array(maxQuads * 12)
  const index = new Uint16Array(maxQuads * 6)
  let q = 0

  const quad = (x0: number, z0: number, x1: number, z1: number, y: number, c: [number, number, number]) => {
    const v = q * 12
    position.set([x0, y, z0, x1, y, z0, x1, y, z1, x0, y, z1], v)
    for (let i = 0; i < 4; i++) {
      normal[v + i * 3 + 1] = 1
      color.set(c, v + i * 3)
    }
    const b = q * 4
    index.set([b, b + 2, b + 1, b, b + 3, b + 2], q * 6) // CCW seen from +y
    q++
  }

  const ox = chunk.chunkX * CHUNK_SIZE
  const oz = chunk.chunkY * CHUNK_SIZE
  for (let ly = 0; ly < CHUNK_SIZE; ly++) {
    for (let lx = 0; lx < CHUNK_SIZE; lx++) {
      const i = tileIndex(lx, ly)
      const x = ox + lx
      const z = oz + ly
      quad(x, z, x + 1, z + 1, Y_TERRAIN, rgb(TERRAIN_COLOR[chunk.terrainTiles[i]] ?? TERRAIN_COLOR[Terrain.GRASS]))

      const road = chunk.roadTiles[i]
      if (road === 0) continue
      const cls = (road >> 5) === RoadClass.ARTERIAL ? 1 : 0
      const conn = road & 31
      const rc = rgb(ROAD_COLOR[cls])
      const mc = rgb(MARK_COLOR[cls])
      quad(x, z, x + 1, z + 1, Y_ROAD, rc)
      if (conn === ROAD_ISOLATED) {
        quad(x + 0.42, z + 0.42, x + 0.58, z + 0.58, Y_MARK, mc)
        continue
      }
      for (const [bit, [a, b, c, d]] of MARKS) if (conn & bit) quad(x + a, z + b, x + c, z + d, Y_MARK, mc)
    }
  }

  return {
    position: position.slice(0, q * 12),
    normal: normal.slice(0, q * 12),
    color: color.slice(0, q * 12),
    index: index.slice(0, q * 6),
  }
}
