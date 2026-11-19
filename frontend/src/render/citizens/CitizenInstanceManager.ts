import * as THREE from 'three'
import { createCitizenGeometry, createCitizenMaterial } from './citizenGeometry'
import type { CitizenSystem } from './CitizenSystem'
import { CITIZEN_Y } from './MovementSystem'

const PALETTE = [new THREE.Color(0x3fa34d), new THREE.Color(0xd9534f), new THREE.Color(0x8a8f98)]
const SELECTED = new THREE.Color(0xffd400)
const SELECTED_SCALE = 1.5

const m = new THREE.Matrix4()
const pos = new THREE.Vector3()
const quat = new THREE.Quaternion()
const scl = new THREE.Vector3()
const up = new THREE.Vector3(0, 1, 0)

export class CitizenInstanceManager {
  readonly mesh: THREE.InstancedMesh
  private readonly geometry = createCitizenGeometry()
  private readonly material = createCitizenMaterial()
  private slots: Int32Array = new Int32Array(0)
  private system: CitizenSystem | null = null

  constructor(capacity: number) {
    this.mesh = new THREE.InstancedMesh(this.geometry, this.material, Math.max(capacity, 1))
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
    // instanceColor must exist before the first render (else shader variant recompiles)
    this.mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(Math.max(capacity, 1) * 3), 3)
    this.mesh.instanceColor.setUsage(THREE.DynamicDrawUsage)
    // fixed map-covering sphere: never recomputed, never null
    this.mesh.boundingSphere = new THREE.Sphere(new THREE.Vector3(256, 0, 256), 365)
    this.mesh.frustumCulled = false
    this.mesh.userData.citizen = true // tag for __lcDebug.citizenMeshes()
    this.mesh.count = 0
    this.mesh.visible = false
  }

  write(system: CitizenSystem, selectedIndex: number): void {
    this.system = system
    this.slots = system.slots
    const mesh = this.mesh
    const n = Math.min(system.visibleCount, mesh.instanceMatrix.count)
    const { x, z, heading } = system.movement
    for (let k = 0; k < n; k++) {
      const i = system.slots[k]
      const sel = i === selectedIndex
      pos.set(x[i], CITIZEN_Y, z[i])
      quat.setFromAxisAngle(up, heading[i])
      const s = sel ? SELECTED_SCALE : 1
      scl.set(s, s, s)
      m.compose(pos, quat, scl)
      mesh.setMatrixAt(k, m)
      mesh.setColorAt(k, sel ? SELECTED : PALETTE[system.colorIdx[i]])
    }
    mesh.count = n
    mesh.visible = n > 0
    if (n > 0) {
      mesh.instanceMatrix.clearUpdateRanges()
      mesh.instanceMatrix.addUpdateRange(0, n * 16)
      mesh.instanceMatrix.needsUpdate = true
      const c = mesh.instanceColor!
      c.clearUpdateRanges()
      c.addUpdateRange(0, n * 3)
      c.needsUpdate = true
    }
  }

  citizenIdAt(instanceId: number): string | null {
    const i = this.slots[instanceId]
    return this.system?.store.citizens[i]?.id ?? null
  }

  dispose(): void {
    this.mesh.removeFromParent()
    this.mesh.dispose()
    this.geometry.dispose()
    this.material.dispose()
  }
}
