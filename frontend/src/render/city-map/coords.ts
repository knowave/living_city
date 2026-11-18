export const MAP_SIZE = 64

export type Vec3 = [x: number, y: number, z: number]

// Tile (x, y) -> world XZ plane, Y up, 1 tile = 1 unit, world origin at the map's top-left corner.
// A w*h rect anchored at (x, y) returns its center; a 1*1 rect is a single tile center.
export function tileRectToWorld(x: number, y: number, w = 1, h = 1): Vec3 {
  return [x + w / 2, 0, y + h / 2]
}

export const MAP_CENTER = tileRectToWorld(0, 0, MAP_SIZE, MAP_SIZE)
