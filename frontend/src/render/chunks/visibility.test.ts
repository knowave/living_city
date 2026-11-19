import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { chunkKey } from '../map/tiles'
import { computeChunkSets } from './visibility'

const CENTER = 256 // 512-tile map center (coords.ts is switched by the integration task)

// Mirrors IsometricCamera: ortho, 45deg yaw, 35.26deg pitch, distance 200, drei frustum = size/2/zoom.
function makeCamera(w: number, h: number, zoom: number, dx = 0) {
  const pitch = Math.atan(1 / Math.SQRT2)
  const yaw = Math.PI / 4
  const cam = new THREE.OrthographicCamera(-w / 2, w / 2, h / 2, -h / 2, 0.1, 1000)
  cam.zoom = zoom
  cam.updateProjectionMatrix()
  const target = new THREE.Vector3(CENTER + dx, 0, CENTER)
  cam.position.set(
    target.x + 200 * Math.cos(pitch) * Math.sin(yaw),
    200 * Math.sin(pitch),
    target.z + 200 * Math.cos(pitch) * Math.cos(yaw),
  )
  cam.lookAt(target)
  cam.updateMatrixWorld()
  return cam
}

describe('computeChunkSets', () => {
  it('stays within bounds at 1280x720 default zoom', () => {
    const s = computeChunkSets(makeCamera(1280, 720, 20))
    expect(s.active.size).toBeLessThanOrEqual(64)
    expect(s.visible.size).toBeGreaterThan(0)
  })
  it('stays within bounds at 1920x1080 and 2560x1440 min zoom', () => {
    const a = computeChunkSets(makeCamera(1920, 1080, 12))
    const b = computeChunkSets(makeCamera(2560, 1440, 12))
    expect(a.active.size).toBeLessThanOrEqual(128)
    expect(b.active.size).toBeLessThanOrEqual(160)
  })
  it('active is visible plus clipped 8-neighbor ring', () => {
    const s = computeChunkSets(makeCamera(1280, 720, 20))
    expect(s.active.size).toBeGreaterThan(s.visible.size)
    for (const k of s.visible) expect(s.active.has(k)).toBe(true)
    for (const k of s.active) {
      const [x, z] = k.split(',').map(Number)
      expect(x).toBeGreaterThanOrEqual(0)
      expect(z).toBeLessThan(16)
      const near = [...s.visible].some((v) => {
        const [vx, vz] = v.split(',').map(Number)
        return Math.abs(vx - x) <= 1 && Math.abs(vz - z) <= 1
      })
      expect(near).toBe(true)
    }
  })
  it('panning +x adds leading chunks and drops trailing ones', () => {
    const a = computeChunkSets(makeCamera(1280, 720, 20, -150))
    const b = computeChunkSets(makeCamera(1280, 720, 20, 150))
    expect([...b.active].some((k) => !a.active.has(k))).toBe(true)
    expect([...a.active].some((k) => !b.active.has(k))).toBe(true)
    expect(b.active.has(chunkKey(15, 8))).toBe(true)
    expect(a.active.has(chunkKey(15, 8))).toBe(false)
  })
  it('resize changes the view key inputs and the result', () => {
    const small = makeCamera(1280, 720, 20)
    const big = makeCamera(2560, 1440, 20)
    expect(small.projectionMatrix.elements).not.toEqual(big.projectionMatrix.elements)
    expect(computeChunkSets(big).visible.size).toBeGreaterThan(computeChunkSets(small).visible.size)
  })
})
