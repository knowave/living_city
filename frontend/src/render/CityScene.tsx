import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { SelectionPanel } from './buildings/SelectionPanel'
import { IsometricCamera } from './camera/IsometricCamera'
import type { ChunkManager } from './chunks/ChunkManager'
import { ChunkLayer } from './chunks/ChunkLayer'
import type { ChunkSets } from './chunks/visibility'
import { CitizenControls, COUNTS, parseCount } from './citizens/CitizenControls'
import { CitizenLayer, type CitizenLayerApi } from './citizens/CitizenLayer'
import { CitizenPanel } from './citizens/CitizenPanel'
import type { Speed } from './citizens/SimClock'
import type { Selection } from './citizens/types'
import { DEFAULT_SEED, generateWorld } from './map/generator'
import { toCityMap } from './map/mapper'
import { DebugHud } from './perf/DebugHud'
import { DebugMeter, type DebugBridge, type DebugStats } from './perf/DebugMeter'
import { useRenderCount } from './perf/renderCount'

export function CityScene() {
  useRenderCount('CityScene')
  const city = useMemo(() => toCityMap(generateWorld(DEFAULT_SEED)), [])
  const [selection, setSelection] = useState<Selection>(null)
  const [count, setCountState] = useState<number>(() => parseCount(new URLSearchParams(location.search).get('citizens')))
  const [speed, setSpeed] = useState<Speed>(1)
  const statsRef = useRef<DebugStats | null>(null)
  const managerRef = useRef<ChunkManager | null>(null)
  const setsRef = useRef<ChunkSets | null>(null)
  const apiRef = useRef<CitizenLayerApi>({ system: null, mesh: null, cpu: { last: 0, avg: 0, max: 0 }, resetCpu() {} })

  const setCount = useCallback((n: number) => {
    if (!COUNTS.includes(n)) return
    setCountState(n)
    setSelection((s) => (s?.kind === 'citizen' ? null : s))
  }, [])
  const selectBuilding = useCallback((id: string) => setSelection({ kind: 'building', id }), [])
  const selectCitizen = useCallback((id: string) => setSelection({ kind: 'citizen', id }), [])

  const bridgeRef = useRef<DebugBridge>({ selection, setCount, setSpeed })
  useEffect(() => {
    bridgeRef.current = { selection, setCount, setSpeed }
  }, [selection, setCount])

  const buildingId = selection?.kind === 'building' ? selection.id : null
  const citizenId = selection?.kind === 'citizen' ? selection.id : null

  return (
    <div className="relative h-full w-full">
      <Canvas onPointerMissed={() => setSelection(null)}>
        <color attach="background" args={['#cfe6f5']} />
        <ambientLight intensity={0.7} />
        <directionalLight position={[40, 80, 20]} intensity={1.2} />
        <IsometricCamera />
        <ChunkLayer city={city} selectedId={buildingId} onSelect={selectBuilding} managerRef={managerRef} setsRef={setsRef} />
        <CitizenLayer
          city={city}
          count={count}
          speed={speed}
          setsRef={setsRef}
          selectedCitizenId={citizenId}
          onSelectCitizen={selectCitizen}
          apiRef={apiRef}
        />
        <DebugMeter managerRef={managerRef} city={city} selectedId={buildingId} statsRef={statsRef} apiRef={apiRef} bridgeRef={bridgeRef} />
      </Canvas>
      <SelectionPanel city={city} selectedId={buildingId} />
      <CitizenPanel citizenId={citizenId} apiRef={apiRef} />
      <CitizenControls count={count} speed={speed} onCount={setCount} onSpeed={setSpeed} />
      <DebugHud statsRef={statsRef} apiRef={apiRef} />
    </div>
  )
}
