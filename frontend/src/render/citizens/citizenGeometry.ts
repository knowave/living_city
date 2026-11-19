import * as THREE from 'three'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'

// Low-poly citizen (~32 tris), base at y=0, shared by all instances.
export function createCitizenGeometry(): THREE.BufferGeometry {
  const body = new THREE.CylinderGeometry(0.28, 0.32, 0.9, 8, 1)
  body.translate(0, 0.45, 0)
  const head = new THREE.OctahedronGeometry(0.22, 0)
  head.translate(0, 1.12, 0)
  const merged = mergeGeometries([body.toNonIndexed(), head.toNonIndexed()])
  body.dispose()
  head.dispose()
  return merged
}

export function createCitizenMaterial(): THREE.MeshLambertMaterial {
  return new THREE.MeshLambertMaterial({ color: 0xffffff })
}
