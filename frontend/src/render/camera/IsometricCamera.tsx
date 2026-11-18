import { MapControls, OrthographicCamera } from '@react-three/drei'
import { MAP_CENTER, MAP_SIZE } from '../city-map/coords'

const PITCH = Math.atan(1 / Math.SQRT2) // ~35.264 deg
const YAW = Math.PI / 4
const DISTANCE = 200 // ortho: distance only affects clipping, not apparent size
const OFFSET: [number, number, number] = [
  DISTANCE * Math.cos(PITCH) * Math.sin(YAW),
  DISTANCE * Math.sin(PITCH),
  DISTANCE * Math.cos(PITCH) * Math.cos(YAW),
]
const POSITION: [number, number, number] = [
  MAP_CENTER[0] + OFFSET[0],
  OFFSET[1],
  MAP_CENTER[2] + OFFSET[2],
]

export const MIN_ZOOM = 6
export const MAX_ZOOM = 60

interface ClampTarget {
  target: { x: number; z: number }
  object: { position: { x: number; z: number } }
}

// Clamp the pan target to the map and move the camera by the same delta so the angle is preserved.
function clampToMap({ target, object }: ClampTarget) {
  const x = Math.min(Math.max(target.x, 0), MAP_SIZE)
  const z = Math.min(Math.max(target.z, 0), MAP_SIZE)
  object.position.x += x - target.x
  object.position.z += z - target.z
  target.x = x
  target.z = z
}

export function IsometricCamera() {
  return (
    <>
      <OrthographicCamera makeDefault position={POSITION} zoom={14} near={0.1} far={1000} />
      <MapControls
        target={MAP_CENTER}
        enableRotate={false}
        zoomToCursor
        minZoom={MIN_ZOOM}
        maxZoom={MAX_ZOOM}
        onChange={(e) => e && clampToMap(e.target as ClampTarget)}
      />
    </>
  )
}
