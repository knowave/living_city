import { MAP_CENTER, MAP_SIZE } from './coords'

export function Terrain() {
  return (
    <>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={MAP_CENTER}>
        <planeGeometry args={[MAP_SIZE, MAP_SIZE]} />
        <meshStandardMaterial color="#6b9a5b" />
      </mesh>
      <gridHelper args={[MAP_SIZE, MAP_SIZE, '#8fb784', '#8fb784']} position={[MAP_CENTER[0], 0.01, MAP_CENTER[2]]} />
    </>
  )
}
