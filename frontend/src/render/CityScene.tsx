import { Canvas } from '@react-three/fiber'
import { Buildings } from './buildings/Buildings'
import { Roads } from './city-map/Roads'
import { Terrain } from './city-map/Terrain'
import { IsometricCamera } from './camera/IsometricCamera'

export function CityScene() {
  return (
    <Canvas>
      <color attach="background" args={['#cfe6f5']} />
      <ambientLight intensity={0.7} />
      <directionalLight position={[40, 80, 20]} intensity={1.2} />
      <IsometricCamera />
      <Terrain />
      <Roads />
      <Buildings />
    </Canvas>
  )
}
