import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { CitizenLayerApi } from '../citizens/CitizenLayer'
import type { CitizenDebugInfo, CitizenPerf } from '../citizens/CitizenSystem'
import type { Speed } from '../citizens/SimClock'
import type { Selection } from '../citizens/types'
import { buildingTransform } from '../buildings/buildingStyle'
import type { ChunkManager } from '../chunks/ChunkManager'
import type { CityMap } from '../map/types'
import { createFpsTracker } from './fps'
import { renderCounts } from './renderCount'
import { MAP_SIZE } from '../map/tiles'

export interface DebugStats {
  fps: number
  avg: number
  activeChunks: number
  pendingChunks: number
  calls: number
  triangles: number
  geometries: number
  textures: number
}

interface PanControls {
  target: THREE.Vector3
  update: () => void
}

declare global {
  interface Window {
    __lcDebug?: {
      stats: () => DebugStats | null
      activeKeys: () => string[]
      panTo: (x: number, z: number) => void
      screenPointOf: (buildingId: string) => { x: number; y: number } | null
      screenPointOfTile: (x: number, y: number) => { x: number; y: number } | null
      selectedId: () => string | null
      setCitizenCount: (n: number) => void
      setSpeed: (s: Speed) => void
      selection: () => Selection
      citizenInfo: (id: string) => (CitizenDebugInfo & { screen: { x: number; y: number } | null }) | null
      citizenScreenPoint: (id: string) => { x: number; y: number } | null
      expectedFresh: (id: string, tick: number) => { x: number; z: number } | null
      clockSample: () => { now: number; tick: number } | null
      citizenMeshes: () => number
      renderCounts: () => Record<string, number>
      citizenStats: () => { total: number; visible: number; cpu: CitizenLayerApi['cpu']; perf: CitizenPerf } | null
      isQuietTile: (x: number, y: number) => boolean
    }
  }
}

export interface DebugBridge {
  selection: Selection
  setCount: (n: number) => void
  setSpeed: (s: Speed) => void
}

interface Props {
  apiRef: { current: CitizenLayerApi }
  bridgeRef: { current: DebugBridge }
  managerRef: { current: ChunkManager | null }
  city: CityMap
  selectedId: string | null
  statsRef: { current: DebugStats | null }
}

export function DebugMeter({ managerRef, city, selectedId, statsRef, apiRef, bridgeRef }: Props) {
  const tracker = useMemo(() => createFpsTracker(), [])
  const latest = useRef<DebugStats | null>(null)
  const selRef = useRef(selectedId)
  const gl = useThree((s) => s.gl)
  const camera = useThree((s) => s.camera)
  const scene = useThree((s) => s.scene)
  const controls = useThree((s) => s.controls) as unknown as PanControls | null

  useEffect(() => {
    selRef.current = selectedId
  }, [selectedId])

  // useFrame runs before gl.render, and three resets gl.info at the start of each render
  // (autoReset), so info.render.* here is the complete previous frame.
  useFrame(() => {
    const fps = tracker.tick(performance.now() / 1000)
    const m = managerRef.current
    if (!fps || !m) return
    const s: DebugStats = {
      ...fps,
      activeChunks: m.activeCount,
      pendingChunks: m.pendingCount,
      calls: gl.info.render.calls,
      triangles: gl.info.render.triangles,
      geometries: gl.info.memory.geometries,
      textures: gl.info.memory.textures,
    }
    latest.current = s
    statsRef.current = s
  })

  useEffect(() => {
    if (!import.meta.env.DEV) return
    const v = new THREE.Vector3()
    const project = (x: number, y: number, z: number) => {
      v.set(x, y, z).project(camera)
      if (Math.abs(v.x) > 1 || Math.abs(v.y) > 1) return null
      const r = gl.domElement.getBoundingClientRect()
      return { x: r.left + ((v.x + 1) / 2) * r.width, y: r.top + ((1 - v.y) / 2) * r.height }
    }
    window.__lcDebug = {
      stats: () => latest.current,
      activeKeys: () => managerRef.current?.activeKeys() ?? [],
      panTo: (x, z) => {
        if (!controls) return
        const dx = x - controls.target.x
        const dz = z - controls.target.z
        controls.target.x += dx
        controls.target.z += dz
        camera.position.x += dx
        camera.position.z += dz
        controls.update()
      },
      screenPointOf: (id) => {
        const b = city.buildingById.get(id)
        if (!b) return null
        const { position, scale } = buildingTransform(b)
        return project(position[0], scale[1] / 2, position[2])
      },
      screenPointOfTile: (x, y) => project(x + 0.5, 0, y + 0.5),
      selectedId: () => selRef.current,
      setCitizenCount: (n) => bridgeRef.current.setCount(n),
      setSpeed: (s) => bridgeRef.current.setSpeed(s),
      selection: () => bridgeRef.current.selection,
      citizenInfo: (id) => {
        const info = apiRef.current.system?.info(id)
        return info ? { ...info, screen: project(info.current.x, 0.4, info.current.z) } : null
      },
      citizenScreenPoint: (id) => {
        const c = apiRef.current.system?.info(id)?.current
        return c ? project(c.x, 0.4, c.z) : null
      },
      expectedFresh: (id, tick) => apiRef.current.system?.expectedFresh(id, tick) ?? null,
      clockSample: () => {
        const sys = apiRef.current.system
        if (!sys) return null
        const now = performance.now()
        return { now, tick: sys.clock.tickAt(now) }
      },
      citizenMeshes: () => {
        let n = 0
        scene.traverse((o) => {
          if (o instanceof THREE.InstancedMesh && o.userData.citizen) n++
        })
        return n
      },
      renderCounts,
      citizenStats: () => {
        const sys = apiRef.current.system
        return sys ? { total: sys.total, visible: sys.visibleCount, cpu: apiRef.current.cpu, perf: sys.perf } : null
      },
      isQuietTile: (x, y) => {
        const sys = apiRef.current.system
        if (!sys) return false
        for (const b of city.buildingById.values())
          if (x >= b.tileX && x < b.tileX + b.width && y >= b.tileY && y < b.tileY + b.height) return false
        for (let dy = -2; dy <= 2; dy++)
          for (let dx = -2; dx <= 2; dx++) {
            const tx = x + dx
            const ty = y + dy
            if (tx < 0 || ty < 0 || tx >= MAP_SIZE || ty >= MAP_SIZE) continue
            if (sys.grid.component[ty * MAP_SIZE + tx] >= 0) return false
          }
        return true
      },
    }
    return () => {
      delete window.__lcDebug
    }
  }, [camera, controls, gl, city, managerRef, scene, apiRef, bridgeRef])

  return null
}
