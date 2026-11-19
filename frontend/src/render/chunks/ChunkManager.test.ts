import * as THREE from 'three'
import { describe, expect, it, vi } from 'vitest'
import { chunkKey } from '../map/tiles'
import { toCityMap } from '../map/mapper'
import type { BuildingDTO, ChunkDTO, ChunkKey } from '../map/types'
import { ChunkManager } from './ChunkManager'
import type { ChunkSets } from './visibility'

const chunkDto = (x: number, y: number): ChunkDTO => ({
  id: `c${x}-${y}`, world_id: 'w', chunk_x: x, chunk_y: y, chunk_size: 32,
  terrain_tiles: new Array(1024).fill(0), road_tiles: new Array(1024).fill(0), schema_version: 1, revision: 0,
})
const bld = (id: string, x: number, y: number, w = 2, type = 'OFFICE'): BuildingDTO => ({
  id, world_id: 'w', type, tile_x: x, tile_y: y, width: w, height: 2, capacity: 1, occupied_capacity: 0, status: 'ACTIVE',
})

function setup(buildings: BuildingDTO[] = []) {
  const chunks: ChunkDTO[] = []
  for (let x = 0; x < 6; x++) for (let y = 0; y < 4; y++) chunks.push(chunkDto(x, y))
  const city = toCityMap({ chunks, buildings }, () => {})
  const root = new THREE.Group()
  return { city, root, mgr: new ChunkManager(root, city) }
}
const sets = (visible: ChunkKey[], ring: ChunkKey[] = []): ChunkSets => ({
  visible: new Set(visible),
  active: new Set([...visible, ...ring]),
  center: [16, 16],
})
const keys = (n: number, start = 0): ChunkKey[] =>
  Array.from({ length: n }, (_, i) => chunkKey((start + i) % 6, Math.floor((start + i) / 6)))
const spyDispose = (o: THREE.EventDispatcher<{ dispose: object }>) => {
  const fn = vi.fn()
  o.addEventListener('dispose', fn)
  return fn
}

describe('ChunkManager', () => {
  it('drains 20 chunks at 8 per update', () => {
    const { mgr } = setup()
    mgr.sync(sets(keys(20)))
    mgr.update()
    expect(mgr.activeCount).toBe(8)
    expect(mgr.pendingCount).toBe(12)
    mgr.update()
    mgr.update()
    expect([mgr.activeCount, mgr.pendingCount]).toEqual([20, 0])
  })

  it('activates visible before ring', () => {
    const { mgr } = setup()
    const ring = keys(10)
    const visible = keys(8, 10)
    mgr.sync(sets(visible, ring))
    mgr.update()
    const root = (mgr as unknown as { active: Map<ChunkKey, unknown> }).active
    expect([...root.keys()].sort()).toEqual([...visible].sort())
  })

  it('removed pending key never activates or creates resources', () => {
    const { mgr, root } = setup()
    mgr.sync(sets(keys(12)))
    mgr.update()
    const activated = [...(mgr as unknown as { active: Map<ChunkKey, unknown> }).active.keys()]
    mgr.sync(sets(activated)) // the 4 still-pending keys leave the target
    expect(mgr.pendingCount).toBe(0)
    const before = root.children.length
    mgr.update()
    expect(root.children.length).toBe(before)
    expect(mgr.activeCount).toBe(8)
  })

  it('deactivate disposes chunk resources only; dispose() frees shared ones once', () => {
    const { mgr, root } = setup([bld('b1', 1, 1)])
    mgr.sync(sets(keys(4)))
    mgr.update()
    const meshes = root.children.slice() as THREE.Mesh[]
    const ground = meshes.filter((m) => !(m as THREE.InstancedMesh).isInstancedMesh)
    const inst = meshes.find((m) => (m as THREE.InstancedMesh).isInstancedMesh) as THREE.InstancedMesh
    const geoSpies = ground.map((m) => spyDispose(m.geometry))
    const instSpy = spyDispose(inst)
    const sharedGeo = spyDispose(inst.geometry)
    const sharedMat = spyDispose(inst.material as THREE.Material)
    const groundMat = spyDispose(ground[0].material as THREE.Material)

    mgr.sync(sets([]))
    expect(root.children.length).toBe(0)
    geoSpies.forEach((s) => expect(s).toHaveBeenCalledTimes(1))
    expect(instSpy).toHaveBeenCalledTimes(1)
    expect(sharedGeo).not.toHaveBeenCalled()
    expect(sharedMat).not.toHaveBeenCalled()
    expect(groundMat).not.toHaveBeenCalled()

    mgr.dispose()
    expect(sharedGeo).toHaveBeenCalledTimes(1)
    expect(sharedMat).toHaveBeenCalledTimes(1)
    expect(groundMat).toHaveBeenCalledTimes(1)
  })

  it('child counts: 0, 1 and 500 buildings', () => {
    const many = Array.from({ length: 500 }, (_, i) => bld(`m${i}`, 32 + (i % 25), 5 + Math.floor(i / 25) % 20, 1))
    const { mgr, root } = setup([bld('one', 70, 5), ...many])
    for (const [key, n] of [['0,0', 1], ['2,0', 2], ['1,0', 2]] as [ChunkKey, number][]) {
      root.clear()
      const m = new ChunkManager(root, (mgr as unknown as { city: never }).city)
      m.sync(sets([key]))
      m.update()
      expect(root.children.length).toBe(n)
      m.dispose()
    }
  })

  it('border building renders only in its anchor chunk', () => {
    const { mgr, root } = setup([bld('edge', 31, 0, 3)])
    mgr.sync(sets(['0,0', '1,0']))
    mgr.update()
    const insts = root.children.filter((c) => (c as THREE.InstancedMesh).isInstancedMesh)
    expect(insts.length).toBe(1)
    expect(insts[0].userData.buildingIds).toEqual(['edge'])
  })

  it('maps instanceId to building id', () => {
    const { mgr, root } = setup([bld('a', 1, 1), bld('b', 5, 5)])
    mgr.sync(sets(['0,0']))
    mgr.update()
    const inst = root.children[1]
    expect(mgr.buildingIdAt(inst, 0)).toBe('a')
    expect(mgr.buildingIdAt(inst, 1)).toBe('b')
    expect(mgr.buildingIdAt(inst, 9)).toBeNull()
    expect(mgr.buildingIdAt(root.children[0], 0)).toBeNull()
  })

  it('setSelected recolors and restores; applies on later activation', () => {
    const { mgr, root } = setup([bld('a', 1, 1, 2, 'OFFICE')])
    mgr.setSelected('a')
    mgr.sync(sets(['0,0']))
    mgr.update()
    const inst = root.children[1] as THREE.InstancedMesh
    const c = new THREE.Color()
    inst.getColorAt(0, c)
    expect(c.getHexString()).toBe(new THREE.Color('#ff4d4d').getHexString())
    mgr.setSelected(null)
    inst.getColorAt(0, c)
    expect(c.getHexString()).toBe(new THREE.Color('#9b8bd1').getHexString())
  })
})
