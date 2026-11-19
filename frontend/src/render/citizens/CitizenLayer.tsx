import { useFrame, type ThreeEvent } from '@react-three/fiber'
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import type { ChunkSets } from '../chunks/visibility'
import { DEFAULT_SEED } from '../map/generator'
import type { CityMap } from '../map/types'
import { useRenderCount } from '../perf/renderCount'
import { CitizenInstanceManager } from './CitizenInstanceManager'
import { CitizenSystem } from './CitizenSystem'
import type { Speed } from './SimClock'

export interface CitizenLayerApi {
  system: CitizenSystem | null
  mesh: THREE.InstancedMesh | null
  cpu: { last: number; avg: number; max: number } // ms of all per-frame citizen work, avg over last 60 frames
  resetCpu(): void
}

export interface CitizenLayerProps {
  city: CityMap
  count: number // 0 | 100 | 500 | 1000
  speed: Speed
  setsRef: { current: ChunkSets | null }
  selectedCitizenId: string | null
  onSelectCitizen: (id: string) => void
  apiRef: { current: CitizenLayerApi }
}

const WINDOW = 60

export function CitizenLayer({ city, count, speed, setsRef, selectedCitizenId, onSelectCitizen, apiRef }: CitizenLayerProps) {
  useRenderCount('CitizenLayer')
  const groupRef = useRef<THREE.Group>(null)
  const managerRef = useRef<CitizenInstanceManager | null>(null)
  const speedRef = useRef(speed)
  const selectedRef = useRef(selectedCitizenId)
  const samples = useRef<number[]>([])

  useEffect(() => {
    speedRef.current = speed
    selectedRef.current = selectedCitizenId
  })

  useEffect(() => {
    const api = apiRef.current
    api.resetCpu = () => {
      api.cpu.last = api.cpu.avg = api.cpu.max = 0
      samples.current = []
    }
    return () => {
      api.system = null
      api.mesh = null
    }
  }, [apiRef])

  useEffect(() => {
    const api = apiRef.current
    const system = new CitizenSystem(city, DEFAULT_SEED, count, performance.now(), speedRef.current)
    const manager = new CitizenInstanceManager(count)
    groupRef.current!.add(manager.mesh)
    managerRef.current = manager
    api.system = system
    api.mesh = manager.mesh
    api.resetCpu()
    return () => {
      manager.dispose()
      managerRef.current = null
      api.system = null
      api.mesh = null
    }
  }, [city, count, apiRef])

  useEffect(() => {
    apiRef.current.system?.setSpeed(speed, performance.now())
  }, [speed, city, count, apiRef])

  useFrame(() => {
    const api = apiRef.current
    const system = api.system
    const manager = managerRef.current
    if (!system || !manager) return
    const t0 = performance.now()
    system.frame(t0, setsRef.current)
    const sel = selectedRef.current
    manager.write(system, sel ? (system.store.index.get(sel) ?? -1) : -1)
    const dt = performance.now() - t0
    const s = samples.current
    s.push(dt)
    if (s.length > WINDOW) s.shift()
    api.cpu.last = dt
    api.cpu.avg = s.reduce((a, b) => a + b, 0) / s.length
    if (dt > api.cpu.max) api.cpu.max = dt
  })

  const onClick = (e: ThreeEvent<MouseEvent>) => {
    if (e.delta > 4 || e.instanceId === undefined) return
    const id = managerRef.current?.citizenIdAt(e.instanceId)
    if (!id) return
    e.stopPropagation()
    onSelectCitizen(id)
  }

  return <group ref={groupRef} onClick={onClick} />
}
