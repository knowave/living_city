import { CHUNK_SIZE, CHUNKS_PER_SIDE, type ChunkKey } from '../map/types'

export const MASK_SIZE = CHUNKS_PER_SIDE * CHUNKS_PER_SIDE

// out[cx*16+cz] = 1 for each key "cx,cz"
export function chunkMask(keys: Set<ChunkKey>, out: Uint8Array): void {
  out.fill(0)
  for (const key of keys) {
    const [cx, cz] = key.split(',').map(Number)
    out[cx * CHUNKS_PER_SIDE + cz] = 1
  }
}

export function inMask(mask: Uint8Array, x: number, z: number): boolean {
  const cx = Math.floor(x / CHUNK_SIZE)
  const cz = Math.floor(z / CHUNK_SIZE)
  return cx >= 0 && cz >= 0 && cx < CHUNKS_PER_SIDE && cz < CHUNKS_PER_SIDE && mask[cx * CHUNKS_PER_SIDE + cz] === 1
}
