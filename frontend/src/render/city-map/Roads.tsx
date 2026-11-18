import { useLayoutEffect, useRef } from 'react'
import { Object3D } from 'three'
import type { InstancedMesh } from 'three'
import { MAP_SIZE, tileRectToWorld } from './coords'

// Sample data: one east-west street (row 20) and one north-south street (column 30).
const ROAD_TILES: [number, number][] = Array.from({ length: MAP_SIZE }, (_, i): [number, number][] => [
  [i, 20],
  [30, i],
]).flat()
// Dedupe the crossing tile.
const UNIQUE_ROADS = [...new Map(ROAD_TILES.map((t) => [t.join(','), t])).values()]

export const ROAD_ROW = 20
export const ROAD_COL = 30

export function Roads() {
  const ref = useRef<InstancedMesh>(null)
  useLayoutEffect(() => {
    const mesh = ref.current
    if (!mesh) return
    const dummy = new Object3D()
    UNIQUE_ROADS.forEach(([x, y], i) => {
      const [wx, , wz] = tileRectToWorld(x, y)
      dummy.position.set(wx, 0.02, wz)
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)
    })
    mesh.instanceMatrix.needsUpdate = true
  }, [])
  return (
    <instancedMesh ref={ref} args={[undefined, undefined, UNIQUE_ROADS.length]}>
      <boxGeometry args={[1, 0.04, 1]} />
      <meshStandardMaterial color="#3a3d42" />
    </instancedMesh>
  )
}
