import { useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { Buildings } from './buildings/Buildings'
import { SelectionPanel } from './buildings/SelectionPanel'
import { Roads } from './city-map/Roads'
import { Terrain } from './city-map/Terrain'
import { IsometricCamera } from './camera/IsometricCamera'
import { FpsMeter } from './perf/FpsMeter'
import { FpsPanel } from './perf/FpsPanel'
import type { FpsStats } from './perf/fps'

export function CityScene() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [fps, setFps] = useState<FpsStats | null>(null)

  return (
    <div className="relative h-full w-full">
      <Canvas onPointerMissed={(e) => setSelectedId((id) => (e.type === 'click' ? null : id))}>
        <color attach="background" args={['#cfe6f5']} />
        <ambientLight intensity={0.7} />
        <directionalLight position={[40, 80, 20]} intensity={1.2} />
        <IsometricCamera />
        {/* terrain swallows raycasts, so clear selection here; buildings stopPropagation */}
        <group onClick={(e) => e.delta <= 4 && setSelectedId(null)}>
          <Terrain />
        </group>
        <Roads />
        <Buildings selectedId={selectedId} onSelect={setSelectedId} />
        <FpsMeter onUpdate={setFps} />
      </Canvas>
      <SelectionPanel selectedId={selectedId} />
      <FpsPanel stats={fps} />
    </div>
  )
}
