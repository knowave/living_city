import { describe, expect, it } from 'vitest'
import { CitizenStore } from './CitizenStore'
import { toCitizen } from './mapper'
import type { CitizenDTO } from './types'

const mk = (id: string) =>
  toCitizen({
    id, world_id: 'w', household_id: null, name: id, age: 1, home_building_id: 'b1', current_building_id: 'b1',
    employment_status: 'EMPLOYED', employer_id: null, happiness: 1, health: 1, skills: {}, risk_tolerance: 0,
    consumption_preference: 0, current_activity: 'IDLE', current_destination: null, arrival_tick: null, cash_balance: null,
  } satisfies CitizenDTO)

const move = { citizenId: 'a', fromBuildingId: 'b1', toBuildingId: 'b2', startTick: 0, arrivalTick: 4 }

describe('CitizenStore', () => {
  it('indexes citizens and starts idle with no coordinates', () => {
    const s = new CitizenStore([mk('a'), mk('b')])
    expect(s.index.get('b')).toBe(1)
    expect(s.moving).toEqual([null, null])
    for (const k of ['x', 'y', 'z', 'position']) expect(k in s.citizens[0]).toBe(false)
  })
  it('applyMovement then applyArrival round-trips state', () => {
    const s = new CitizenStore([mk('a')])
    s.applyMovement(move)
    expect(s.moving[0]).toBe(move)
    expect(s.citizens[0]).toMatchObject({ currentActivity: 'MOVING', currentDestination: 'b2', arrivalTick: 4 })
    s.applyArrival('a', 'b2')
    expect(s.moving[0]).toBeNull()
    expect(s.citizens[0]).toMatchObject({
      currentActivity: 'IDLE', currentBuildingId: 'b2', currentDestination: null, arrivalTick: null,
    })
  })
  it('ignores unknown citizens', () => {
    const s = new CitizenStore([mk('a')])
    s.applyMovement({ ...move, citizenId: 'zz' })
    s.applyArrival('zz', 'b2')
    expect(s.moving[0]).toBeNull()
  })
})
