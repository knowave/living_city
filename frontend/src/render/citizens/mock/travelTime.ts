// temporary mock of Python engine rule (docs/02-domain/03-citizen.md §4.4); not permanent frontend domain logic.
// The Python engine owns this formula; Phase 4~5 replaces it with departure/arrival ticks from the engine.
// Render/movement modules must not import this file (citizenSystem.test.ts checks).
import { MAP_SIZE } from '../../map/tiles'

export const TILES_PER_TICK = 40 // domain rule: tiles a citizen moves per simulation tick

const N = MAP_SIZE

// entrance road tile -> entrance road tile, tile index = y*512+x
export function travelTicks(fromTile: number, toTile: number): number {
  const d = Math.abs((fromTile % N) - (toTile % N)) + Math.abs(Math.floor(fromTile / N) - Math.floor(toTile / N))
  return Math.max(1, Math.ceil(d / TILES_PER_TICK))
}
