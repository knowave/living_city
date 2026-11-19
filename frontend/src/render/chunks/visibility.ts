import * as THREE from 'three'
import { CHUNK_SIZE, CHUNKS_PER_SIDE, type ChunkKey } from '../map/types'
import { chunkKey } from '../map/tiles'

export interface ChunkSets {
  visible: Set<ChunkKey>
  active: Set<ChunkKey> // visible + 1-chunk ring, clipped to the map
  center: [x: number, z: number] // view-axis hit on y=0, queue sort anchor
}

const frustum = new THREE.Frustum()
const matrix = new THREE.Matrix4()
const box = new THREE.Box3()
const origin = new THREE.Vector3()
const dir = new THREE.Vector3()

export function computeChunkSets(camera: THREE.Camera, maxHeight = 8): ChunkSets {
  camera.updateMatrixWorld()
  matrix.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse)
  frustum.setFromProjectionMatrix(matrix)

  const visible = new Set<ChunkKey>()
  for (let cx = 0; cx < CHUNKS_PER_SIDE; cx++) {
    for (let cz = 0; cz < CHUNKS_PER_SIDE; cz++) {
      box.min.set(cx * CHUNK_SIZE, 0, cz * CHUNK_SIZE)
      box.max.set((cx + 1) * CHUNK_SIZE, maxHeight, (cz + 1) * CHUNK_SIZE)
      if (frustum.intersectsBox(box)) visible.add(chunkKey(cx, cz))
    }
  }

  const active = new Set<ChunkKey>(visible)
  for (const key of visible) {
    const [cx, cz] = key.split(',').map(Number)
    for (let dx = -1; dx <= 1; dx++) {
      for (let dz = -1; dz <= 1; dz++) {
        const nx = cx + dx
        const nz = cz + dz
        if (nx >= 0 && nz >= 0 && nx < CHUNKS_PER_SIDE && nz < CHUNKS_PER_SIDE) active.add(chunkKey(nx, nz))
      }
    }
  }

  camera.getWorldPosition(origin)
  camera.getWorldDirection(dir)
  const t = dir.y < -1e-6 ? -origin.y / dir.y : 0
  return { visible, active, center: [origin.x + dir.x * t, origin.z + dir.z * t] }
}
