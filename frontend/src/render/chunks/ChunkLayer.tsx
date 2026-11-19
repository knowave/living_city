import { useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import type { CityMap } from '../map/types'
import { ChunkManager } from './ChunkManager'
import { computeChunkSets, type ChunkSets } from './visibility'

interface ChunkLayerProps {
  city: CityMap
  selectedId: string | null
  onSelect: (id: string) => void
  managerRef: { current: ChunkManager | null }
  setsRef?: { current: ChunkSets | null }
}

export function ChunkLayer({ city, selectedId, onSelect, managerRef, setsRef }: ChunkLayerProps) {
  const groupRef = useRef<THREE.Group>(null)
  const camera = useThree((s) => s.camera)
  const lastView = useRef<number[]>([])
  const lastActive = useRef('')

  useEffect(() => {
    const manager = new ChunkManager(groupRef.current!, city)
    managerRef.current = manager
    lastView.current = []
    lastActive.current = ''
    return () => {
      manager.dispose()
      managerRef.current = null
    }
  }, [city, managerRef])

  useEffect(() => {
    managerRef.current?.setSelected(selectedId)
  }, [city, selectedId, managerRef])

  useFrame(() => {
    const manager = managerRef.current
    if (!manager) return
    // projection (resize/zoom) + world matrix (pan) cover every view change
    const view = [...camera.projectionMatrix.elements, ...camera.matrixWorld.elements]
    if (view.some((v, i) => v !== lastView.current[i])) {
      lastView.current = view
      const sets = computeChunkSets(camera)
      if (setsRef) setsRef.current = sets
      const activeKey = [...sets.active].join('|')
      if (activeKey !== lastActive.current) {
        lastActive.current = activeKey
        manager.sync(sets)
      }
    }
    manager.update() // every frame: drains the activation queue
  })

  const onClick = (e: ThreeEvent<MouseEvent>) => {
    if (e.delta > 4) return // drag, not a click
    const id = e.instanceId === undefined ? null : managerRef.current?.buildingIdAt(e.object, e.instanceId)
    if (!id) return
    e.stopPropagation()
    onSelect(id)
  }

  return <group ref={groupRef} onClick={onClick} />
}
