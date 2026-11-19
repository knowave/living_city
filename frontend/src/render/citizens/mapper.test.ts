import { describe, expect, it, vi } from 'vitest'
import citySchema from '../../../../backend/app/schemas/city.py?raw'
import { toCitizen, toMovementEvent } from './mapper'
import { CITIZEN_DTO_KEYS, type CitizenDTO, type MovementEventDTO } from './types'

const dto = (over: Partial<CitizenDTO> = {}): CitizenDTO => ({
  id: 'c1',
  world_id: 'w',
  household_id: null,
  name: 'n',
  age: 30,
  home_building_id: 'b1',
  current_building_id: 'b1',
  employment_status: 'EMPLOYED',
  employer_id: null,
  happiness: 50,
  health: 50,
  skills: {},
  risk_tolerance: 0.5,
  consumption_preference: 0.5,
  current_activity: 'IDLE',
  current_destination: null,
  arrival_tick: null,
  cash_balance: null,
  ...over,
})
const ev = (over: Partial<MovementEventDTO> = {}): MovementEventDTO => ({
  citizen_id: 'c1',
  from_building_id: 'b1',
  to_building_id: 'b2',
  start_tick: 0,
  arrival_tick: 5,
  ...over,
})

describe('AC2 CitizenDTO keys', () => {
  it('match backend CitizenRead fields', () => {
    const block = citySchema.split('class CitizenRead')[1].split(/^class /m)[0]
    const fields = [...block.matchAll(/^ {4}(\w+):/gm)].map((m) => m[1]).filter((f) => f !== 'model_config')
    expect(new Set(Object.keys(CITIZEN_DTO_KEYS))).toEqual(new Set(fields))
  })
})

describe('toCitizen', () => {
  it('maps snake_case to camelCase without coordinates', () => {
    const c = toCitizen(dto({ cash_balance: 7, current_destination: 'b2', arrival_tick: 3 }))
    expect(c).toMatchObject({ worldId: 'w', homeBuildingId: 'b1', cashBalance: 7, currentDestination: 'b2', arrivalTick: 3 })
    for (const k of ['x', 'y', 'z', 'position']) expect(k in c).toBe(false)
  })
  it('tolerates unknown enums and reports each kind', () => {
    const cb = vi.fn()
    const c = toCitizen(dto({ employment_status: 'RETIRED', current_activity: 'DANCING' }), cb)
    expect(c.employmentStatus).toBe('RETIRED')
    expect(cb).toHaveBeenCalledTimes(2)
    toCitizen(dto(), cb)
    expect(cb).toHaveBeenCalledTimes(2)
  })
})

describe('toMovementEvent', () => {
  it('maps a valid event', () => {
    expect(toMovementEvent(ev())).toEqual({
      citizenId: 'c1', fromBuildingId: 'b1', toBuildingId: 'b2', startTick: 0, arrivalTick: 5,
    })
  })
  it.each([
    ['non-integer tick', { start_tick: 0.5 }],
    ['arrival <= start', { arrival_tick: 0 }],
    ['empty id', { citizen_id: '' }],
  ])('rejects %s with one warning', (_n, over) => {
    const warn = vi.fn()
    expect(toMovementEvent(ev(over), warn)).toBeNull()
    expect(warn).toHaveBeenCalledTimes(1)
  })
})
