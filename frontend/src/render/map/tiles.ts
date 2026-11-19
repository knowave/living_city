import { CHUNK_SIZE, type ChunkKey } from './types'

export const Terrain = { GRASS: 0, WATER: 1, SAND: 2 } as const
export const RoadClass = { LOCAL: 0, ARTERIAL: 1 } as const
export const Dir = { N: 1, E: 2, S: 4, W: 8 } as const
export const ROAD_ISOLATED = 16
export const MAP_SIZE = 512

export function tileIndex(localX: number, localY: number): number {
  return localY * CHUNK_SIZE + localX
}

export function worldToChunk(tileX: number, tileY: number) {
  const chunkX = Math.floor(tileX / CHUNK_SIZE)
  const chunkY = Math.floor(tileY / CHUNK_SIZE)
  return { chunkX, chunkY, localX: tileX - chunkX * CHUNK_SIZE, localY: tileY - chunkY * CHUNK_SIZE }
}

export function chunkLocalToWorld(chunkX: number, chunkY: number, localX: number, localY: number) {
  return { tileX: chunkX * CHUNK_SIZE + localX, tileY: chunkY * CHUNK_SIZE + localY }
}

export function chunkKey(chunkX: number, chunkY: number): ChunkKey {
  return `${chunkX},${chunkY}`
}

export function encodeRoad(cls: number, connection: number): number {
  return (cls << 5) | connection
}

export function decodeRoad(v: number): { cls: number; connection: number } | null {
  return v === 0 ? null : { cls: v >> 5, connection: v & 31 }
}

export function isKnownRoad(v: number): boolean {
  if (v === 0) return true
  if (!Number.isInteger(v) || v < 0) return false
  const cls = v >> 5
  const conn = v & 31
  return cls <= RoadClass.ARTERIAL && conn >= 1 && conn <= ROAD_ISOLATED
}

export function isKnownTerrain(v: number): boolean {
  return v === Terrain.GRASS || v === Terrain.WATER || v === Terrain.SAND
}
