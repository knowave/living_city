import { CitizenActivity, type Citizen, type MovementEvent } from './types'

// Logical state only; no coordinates. Positions derive from (event, tick, path).
export class CitizenStore {
  readonly citizens: Citizen[]
  readonly index = new Map<string, number>()
  readonly moving: (MovementEvent | null)[]

  constructor(list: Citizen[]) {
    this.citizens = list
    this.moving = list.map(() => null)
    list.forEach((c, i) => this.index.set(c.id, i))
  }

  applyMovement(e: MovementEvent): void {
    const i = this.index.get(e.citizenId)
    if (i === undefined) return
    const c = this.citizens[i]
    this.moving[i] = e
    c.currentActivity = CitizenActivity.MOVING
    c.currentDestination = e.toBuildingId
    c.arrivalTick = e.arrivalTick
  }

  applyArrival(citizenId: string, buildingId: string): void {
    const i = this.index.get(citizenId)
    if (i === undefined) return
    const c = this.citizens[i]
    this.moving[i] = null
    c.currentActivity = CitizenActivity.IDLE
    c.currentBuildingId = buildingId
    c.currentDestination = null
    c.arrivalTick = null
  }
}
