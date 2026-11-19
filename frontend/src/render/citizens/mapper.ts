import {
  CitizenActivity,
  EmploymentStatus,
  type Citizen,
  type CitizenDTO,
  type MovementEvent,
  type MovementEventDTO,
} from './types'

const warned = new Set<string>()
const warnOnce = (kind: string, value: string) => {
  if (warned.has(kind)) return
  warned.add(kind)
  console.warn(`citizen: unknown ${kind} "${value}" (default style)`)
}

// Unknown enum values are kept as-is; consumers fall back to the default style.
export function toCitizen(
  dto: CitizenDTO,
  onUnknown: (kind: string, value: string) => void = warnOnce,
): Citizen {
  if (!Object.values<string>(EmploymentStatus).includes(dto.employment_status)) {
    onUnknown('employment_status', dto.employment_status)
  }
  if (!Object.values<string>(CitizenActivity).includes(dto.current_activity)) {
    onUnknown('current_activity', dto.current_activity)
  }
  return {
    id: dto.id,
    worldId: dto.world_id,
    householdId: dto.household_id,
    name: dto.name,
    age: dto.age,
    homeBuildingId: dto.home_building_id,
    currentBuildingId: dto.current_building_id,
    employmentStatus: dto.employment_status,
    employerId: dto.employer_id,
    happiness: dto.happiness,
    health: dto.health,
    skills: dto.skills,
    riskTolerance: dto.risk_tolerance,
    consumptionPreference: dto.consumption_preference,
    currentActivity: dto.current_activity,
    currentDestination: dto.current_destination,
    arrivalTick: dto.arrival_tick,
    cashBalance: dto.cash_balance,
  }
}

export function toMovementEvent(
  dto: MovementEventDTO,
  warn: (m: string) => void = console.warn,
): MovementEvent | null {
  const bad = (why: string) => {
    warn(`movement event rejected: ${why}`)
    return null
  }
  if (!dto.citizen_id || !dto.from_building_id || !dto.to_building_id) return bad('empty id')
  if (!Number.isInteger(dto.start_tick) || !Number.isInteger(dto.arrival_tick)) return bad('non-integer tick')
  if (dto.arrival_tick <= dto.start_tick) return bad('arrival_tick <= start_tick')
  return {
    citizenId: dto.citizen_id,
    fromBuildingId: dto.from_building_id,
    toBuildingId: dto.to_building_id,
    startTick: dto.start_tick,
    arrivalTick: dto.arrival_tick,
  }
}
