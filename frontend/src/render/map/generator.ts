import { mulberry32, uuidV4 } from './prng'
import { Dir, MAP_SIZE, RoadClass, Terrain, encodeRoad, tileIndex } from './tiles'
import { CHUNKS_PER_SIDE, CHUNK_SIZE, TILES_PER_CHUNK, TILE_SCHEMA_VERSION, type BuildingDTO, type ChunkDTO } from './types'

export const MOCK_BUILDING_STATUS = 'ACTIVE'
export const DEFAULT_SEED = 1

const N = MAP_SIZE
// user asked 1.2; >1 is equivalent to 1.0 (every candidate attempted)
const BUILDING_ATTEMPT_PROBABILITY = 1.0
const ROAD_NONE = 0
const ROAD_LOCAL = 1
const ROAD_ARTERIAL = 2

// type, weight, min size, max size, capacity per tile
const BUILDING_SPECS = [
  { type: 'RESIDENTIAL', weight: 0.5, min: 2, max: 3, perTile: 4 },
  { type: 'COMMERCIAL', weight: 0.25, min: 2, max: 4, perTile: 6 },
  { type: 'OFFICE', weight: 0.15, min: 3, max: 4, perTile: 10 },
  { type: 'PUBLIC', weight: 0.1, min: 3, max: 6, perTile: 8 },
] as const

export function generateWorld(seed: number): { chunks: ChunkDTO[]; buildings: BuildingDTO[] } {
  const rng = mulberry32(seed)
  const randInt = (min: number, max: number) => min + Math.floor(rng() * (max - min + 1))
  const worldId = uuidV4(rng)

  // water + sand: noisy lakes, meandering rivers, beach band, small sand patches
  const terrain = new Uint8Array(N * N)
  const NG = N / 16 + 2
  const grid = Array.from({ length: NG * NG }, () => rng())
  const noise = (x: number, y: number) => {
    const fx = x / 16
    const fy = y / 16
    const ix = Math.floor(fx)
    const iy = Math.floor(fy)
    const tx = fx - ix
    const ty = fy - iy
    const g = (dx: number, dy: number) => grid[(iy + dy) * NG + ix + dx]
    return (g(0, 0) * (1 - tx) + g(1, 0) * tx) * (1 - ty) + (g(0, 1) * (1 - tx) + g(1, 1) * tx) * ty
  }
  const lakes = randInt(9, 13)
  for (let i = 0; i < lakes; i++) {
    const r = randInt(12, 30)
    const cx = randInt(0, N - 1)
    const cy = randInt(0, N - 1)
    for (let y = Math.max(0, cy - 2 * r); y <= Math.min(N - 1, cy + 2 * r); y++)
      for (let x = Math.max(0, cx - 2 * r); x <= Math.min(N - 1, cx + 2 * r); x++)
        if (Math.hypot(x - cx, y - cy) <= r * (0.6 + 0.8 * noise(x, y))) terrain[y * N + x] = Terrain.WATER
  }
  const rivers = randInt(2, 3)
  for (let i = 0; i < rivers; i++) {
    const vertical = i % 2 === 1
    const base = randInt(40, N - 40)
    const amp = randInt(20, 50)
    const wavelength = randInt(100, 200)
    const phase = rng() * Math.PI * 2
    const halfW = randInt(2, 3)
    for (let t = 0; t < N; t++) {
      const c = Math.round(base + amp * Math.sin(phase + (t * 2 * Math.PI) / wavelength) + 12 * (noise(t, base) - 0.5))
      for (let d = -halfW; d <= halfW; d++) {
        const x = vertical ? c + d : t
        const y = vertical ? t : c + d
        if (x >= 0 && y >= 0 && x < N && y < N) terrain[y * N + x] = Terrain.WATER
      }
    }
  }
  const water = terrain.slice()
  for (let y = 0; y < N; y++)
    for (let x = 0; x < N; x++) {
      if (water[y * N + x]) continue
      // beach width 1-3 tiles, varying with noise
      const reach = 1 + Math.floor(noise(x + 500, y) * 3)
      let near = false
      for (let dy = -reach; dy <= reach && !near; dy++)
        for (let dx = -reach; dx <= reach; dx++) {
          const nx = x + dx
          const ny = y + dy
          if (nx >= 0 && ny >= 0 && nx < N && ny < N && water[ny * N + nx]) {
            near = true
            break
          }
        }
      if (near) terrain[y * N + x] = Terrain.SAND
    }
  const patches = randInt(20, 30)
  for (let i = 0; i < patches; i++) {
    const r = randInt(3, 7)
    const cx = randInt(0, N - 1)
    const cy = randInt(0, N - 1)
    for (let y = Math.max(0, cy - r); y <= Math.min(N - 1, cy + r); y++)
      for (let x = Math.max(0, cx - r); x <= Math.min(N - 1, cx + r); x++)
        if (terrain[y * N + x] === Terrain.GRASS && (x - cx) ** 2 + (y - cy) ** 2 <= r * r) terrain[y * N + x] = Terrain.SAND
  }

  // roads: arterial grid, then local streets inside blocks
  const road = new Uint8Array(N * N)
  const put = (x: number, y: number, cls: number) => {
    const i = y * N + x
    if ((cls === ROAD_ARTERIAL || terrain[i] !== Terrain.WATER) && road[i] === ROAD_NONE) road[i] = cls
  }
  const offX = randInt(16, 48)
  const offY = randInt(16, 48)
  const arterialsX: number[] = [-1]
  const arterialsY: number[] = [-1]
  for (let x = offX; x < N; x += 64) arterialsX.push(x)
  for (let y = offY; y < N; y += 64) arterialsY.push(y)
  arterialsX.push(N)
  arterialsY.push(N)
  for (const x of arterialsX) if (x >= 0 && x < N) for (let y = 0; y < N; y++) put(x, y, ROAD_ARTERIAL)
  for (const y of arterialsY) if (y >= 0 && y < N) for (let x = 0; x < N; x++) put(x, y, ROAD_ARTERIAL)
  for (let bx = 0; bx < arterialsX.length - 1; bx++)
    for (let by = 0; by < arterialsY.length - 1; by++) {
      const [x0, x1] = [arterialsX[bx], arterialsX[bx + 1]]
      const [y0, y1] = [arterialsY[by], arterialsY[by + 1]]
      for (let x = x0 + 16; x < x1 - 1; x += 16)
        if (rng() < 0.6) for (let y = Math.max(0, y0 + 1); y < Math.min(N, y1); y++) put(x, y, ROAD_LOCAL)
      for (let y = y0 + 16; y < y1 - 1; y += 16)
        if (rng() < 0.6) for (let x = Math.max(0, x0 + 1); x < Math.min(N, x1); x++) put(x, y, ROAD_LOCAL)
    }

  // connection bits on the global grid
  const isRoad = (x: number, y: number) => x >= 0 && y >= 0 && x < N && y < N && road[y * N + x] !== ROAD_NONE
  const roadCode = new Uint8Array(N * N)
  for (let y = 0; y < N; y++)
    for (let x = 0; x < N; x++) {
      const c = road[y * N + x]
      if (c === ROAD_NONE) continue
      const conn =
        (isRoad(x, y - 1) ? Dir.N : 0) | (isRoad(x + 1, y) ? Dir.E : 0) | (isRoad(x, y + 1) ? Dir.S : 0) | (isRoad(x - 1, y) ? Dir.W : 0)
      roadCode[y * N + x] = encodeRoad(c === ROAD_ARTERIAL ? RoadClass.ARTERIAL : RoadClass.LOCAL, conn || 16)
    }

  // slice into chunks
  const chunks: ChunkDTO[] = []
  for (let cy = 0; cy < CHUNKS_PER_SIDE; cy++)
    for (let cx = 0; cx < CHUNKS_PER_SIDE; cx++) {
      const terrainTiles = new Array<number>(TILES_PER_CHUNK)
      const roadTiles = new Array<number>(TILES_PER_CHUNK)
      for (let ly = 0; ly < CHUNK_SIZE; ly++)
        for (let lx = 0; lx < CHUNK_SIZE; lx++) {
          const g = (cy * CHUNK_SIZE + ly) * N + cx * CHUNK_SIZE + lx
          terrainTiles[tileIndex(lx, ly)] = terrain[g]
          roadTiles[tileIndex(lx, ly)] = roadCode[g]
        }
      chunks.push({
        id: uuidV4(rng),
        world_id: worldId,
        chunk_x: cx,
        chunk_y: cy,
        chunk_size: CHUNK_SIZE,
        terrain_tiles: terrainTiles,
        road_tiles: roadTiles,
        schema_version: TILE_SCHEMA_VERSION,
        revision: 1,
      })
    }

  // buildings
  const occ = new Uint8Array(N * N)
  const buildings: BuildingDTO[] = []
  for (let y = 0; y < N; y += 2)
    for (let x = 0; x < N; x += 2) {
      if (rng() >= BUILDING_ATTEMPT_PROBABILITY) continue
      let pick = rng()
      const spec = BUILDING_SPECS.find((s) => (pick -= s.weight) < 0) ?? BUILDING_SPECS[0]
      const w = randInt(spec.min, spec.max)
      const h = randInt(spec.min, spec.max)
      if (x + w > N || y + h > N) continue
      let ok = true
      for (let yy = y; yy < y + h && ok; yy++)
        for (let xx = x; xx < x + w; xx++) {
          const i = yy * N + xx
          if (road[i] !== ROAD_NONE || terrain[i] === Terrain.WATER || occ[i]) {
            ok = false
            break
          }
        }
      if (!ok) continue
      let touchesRoad = false
      for (let k = 0; k < w && !touchesRoad; k++) touchesRoad = isRoad(x + k, y - 1) || isRoad(x + k, y + h)
      for (let k = 0; k < h && !touchesRoad; k++) touchesRoad = isRoad(x - 1, y + k) || isRoad(x + w, y + k)
      if (!touchesRoad) continue
      for (let yy = y; yy < y + h; yy++) for (let xx = x; xx < x + w; xx++) occ[yy * N + xx] = 1
      buildings.push({
        id: uuidV4(rng),
        world_id: worldId,
        type: spec.type,
        tile_x: x,
        tile_y: y,
        width: w,
        height: h,
        capacity: w * h * spec.perTile,
        occupied_capacity: 0,
        status: MOCK_BUILDING_STATUS,
      })
    }

  // drop buildings whose entrance road tile is outside the main road component
  const comp = new Int32Array(N * N).fill(-1)
  const sizes: number[] = []
  const stack = new Int32Array(N * N)
  for (let s = 0; s < N * N; s++) {
    if (road[s] === ROAD_NONE || comp[s] >= 0) continue
    let sp = 0
    let size = 0
    stack[sp++] = s
    comp[s] = sizes.length
    while (sp) {
      const t = stack[--sp]
      size++
      const tx = t % N
      const ty = (t - tx) / N
      for (const [nx, ny] of [[tx, ty - 1], [tx + 1, ty], [tx, ty + 1], [tx - 1, ty]])
        if (isRoad(nx, ny) && comp[ny * N + nx] < 0) {
          comp[ny * N + nx] = sizes.length
          stack[sp++] = ny * N + nx
        }
    }
    sizes.push(size)
  }
  const main = sizes.indexOf(Math.max(...sizes))
  // entrance = first road tile: top row, right col, bottom row, left col (same order as citizens/roadGrid)
  const entranceInMain = (b: BuildingDTO) => {
    const { tile_x: x, tile_y: y, width: w, height: h } = b
    const cand: [number, number][] = []
    for (let k = 0; k < w; k++) cand.push([x + k, y - 1])
    for (let k = 0; k < h; k++) cand.push([x + w, y + k])
    for (let k = 0; k < w; k++) cand.push([x + k, y + h])
    for (let k = 0; k < h; k++) cand.push([x - 1, y + k])
    const e = cand.find(([cx, cy]) => isRoad(cx, cy))
    return !!e && comp[e[1] * N + e[0]] === main
  }

  return { chunks, buildings: buildings.filter(entranceInMain) }
}
