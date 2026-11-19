import * as THREE from 'three'
import { buildingTransform, styleOf } from '../buildings/buildingStyle'
import { chunkKey, worldToChunk } from '../map/tiles'
import { CHUNK_SIZE, type ChunkKey, type CityMap } from '../map/types'
import { buildGroundBuffers } from './groundGeometry'
import type { ChunkSets } from './visibility'

export const MAX_ACTIVATIONS_PER_FRAME = 8
const SELECTED_COLOR = new THREE.Color('#ff4d4d')

interface ActiveChunk {
  ground: THREE.Mesh
  buildings: THREE.InstancedMesh | null
}

export class ChunkManager {
  private readonly groundMaterial = new THREE.MeshLambertMaterial({ vertexColors: true })
  private readonly buildingMaterial = new THREE.MeshLambertMaterial()
  private readonly boxGeometry = new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0)
  private readonly active = new Map<ChunkKey, ActiveChunk>()
  private queue: ChunkKey[] = []
  private selectedId: string | null = null

  private readonly root: THREE.Group
  private readonly city: CityMap

  constructor(root: THREE.Group, city: CityMap) {
    this.root = root
    this.city = city
  }

  get activeCount(): number {
    return this.active.size
  }

  get pendingCount(): number {
    return this.queue.length
  }

  activeKeys(): ChunkKey[] {
    return [...this.active.keys()]
  }

  sync(sets: ChunkSets): void {
    for (const key of [...this.active.keys()]) if (!sets.active.has(key)) this.deactivate(key)
    const queued = new Set(this.queue.filter((k) => sets.active.has(k)))
    for (const key of sets.active) {
      if (!this.active.has(key) && this.city.chunks.has(key)) queued.add(key)
    }
    const [cx, cz] = sets.center
    const dist = (key: ChunkKey) => {
      const [x, z] = key.split(',').map(Number)
      return Math.hypot((x + 0.5) * CHUNK_SIZE - cx, (z + 0.5) * CHUNK_SIZE - cz)
    }
    this.queue = [...queued].sort((a, b) => {
      const va = sets.visible.has(a) ? 0 : 1
      const vb = sets.visible.has(b) ? 0 : 1
      return va - vb || dist(a) - dist(b)
    })
  }

  update(): void {
    for (const key of this.queue.splice(0, MAX_ACTIVATIONS_PER_FRAME)) this.activate(key)
  }

  setSelected(buildingId: string | null): void {
    const prev = this.selectedId
    this.selectedId = buildingId
    if (prev) this.recolor(prev)
    if (buildingId) this.recolor(buildingId)
  }

  buildingIdAt(object: THREE.Object3D, instanceId: number): string | null {
    const ids = object.userData.buildingIds as string[] | undefined
    return ids?.[instanceId] ?? null
  }

  dispose(): void {
    for (const key of [...this.active.keys()]) this.deactivate(key)
    this.queue = []
    this.groundMaterial.dispose()
    this.buildingMaterial.dispose()
    this.boxGeometry.dispose()
  }

  private colorOf(id: string, fallback: string): THREE.Color {
    return id === this.selectedId ? SELECTED_COLOR : new THREE.Color(fallback)
  }

  private recolor(buildingId: string): void {
    const b = this.city.buildingById.get(buildingId)
    if (!b) return
    const { chunkX, chunkY } = worldToChunk(b.tileX, b.tileY)
    const mesh = this.active.get(chunkKey(chunkX, chunkY))?.buildings
    if (!mesh) return
    const i = (mesh.userData.buildingIds as string[]).indexOf(buildingId)
    if (i < 0) return
    mesh.setColorAt(i, this.colorOf(b.id, styleOf(b).color))
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  }

  private activate(key: ChunkKey): void {
    const chunk = this.city.chunks.get(key)
    if (!chunk || this.active.has(key)) return

    const buffers = buildGroundBuffers(chunk)
    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.BufferAttribute(buffers.position, 3))
    geometry.setAttribute('normal', new THREE.BufferAttribute(buffers.normal, 3))
    geometry.setAttribute('color', new THREE.BufferAttribute(buffers.color, 3))
    geometry.setIndex(new THREE.BufferAttribute(buffers.index, 1))
    geometry.computeBoundingSphere()
    const ground = new THREE.Mesh(geometry, this.groundMaterial)
    ground.raycast = () => {} // clicks only hit buildings
    this.root.add(ground)

    let buildings: THREE.InstancedMesh | null = null
    const list = this.city.buildingsByChunk.get(key)
    if (list && list.length > 0) {
      buildings = new THREE.InstancedMesh(this.boxGeometry, this.buildingMaterial, list.length)
      const m = new THREE.Matrix4()
      const q = new THREE.Quaternion()
      list.forEach((b, i) => {
        const { position, scale } = buildingTransform(b)
        m.compose(new THREE.Vector3(...position), q, new THREE.Vector3(...scale))
        buildings!.setMatrixAt(i, m)
        buildings!.setColorAt(i, this.colorOf(b.id, styleOf(b).color))
      })
      buildings.userData.buildingIds = list.map((b) => b.id)
      buildings.computeBoundingSphere()
      this.root.add(buildings)
    }
    this.active.set(key, { ground, buildings })
  }

  private deactivate(key: ChunkKey): void {
    const entry = this.active.get(key)
    if (!entry) return
    this.root.remove(entry.ground)
    entry.ground.geometry.dispose()
    if (entry.buildings) {
      this.root.remove(entry.buildings)
      entry.buildings.dispose() // shared geometry/material stay alive
    }
    this.active.delete(key)
  }
}
