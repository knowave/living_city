// DTO: backend CitizenRead (backend/app/schemas/city.py), snake_case 1:1
export interface CitizenDTO {
  id: string
  world_id: string
  household_id: string | null
  name: string
  age: number
  home_building_id: string | null
  current_building_id: string | null
  employment_status: string // trust boundary: value list TBD, mapper tolerates unknown
  employer_id: string | null
  happiness: number
  health: number
  skills: Record<string, unknown>
  risk_tolerance: number
  consumption_preference: number
  current_activity: string // trust boundary: value list TBD, mapper tolerates unknown
  current_destination: string | null
  arrival_tick: number | null
  cash_balance: number | null
}

// AC2: runtime key list, compared against the backend CitizenRead fields in tests
export const CITIZEN_DTO_KEYS = {
  id: true,
  world_id: true,
  household_id: true,
  name: true,
  age: true,
  home_building_id: true,
  current_building_id: true,
  employment_status: true,
  employer_id: true,
  happiness: true,
  health: true,
  skills: true,
  risk_tolerance: true,
  consumption_preference: true,
  current_activity: true,
  current_destination: true,
  arrival_tick: true,
  cash_balance: true,
} satisfies Record<keyof CitizenDTO, true>

// Mock-only values (G1). The real value lists are TBD in the docs.
export const EmploymentStatus = { EMPLOYED: 'EMPLOYED', UNEMPLOYED: 'UNEMPLOYED' } as const
export const CitizenActivity = { IDLE: 'IDLE', MOVING: 'MOVING' } as const

// Logical state: no coordinates (positions are derived from event + tick + path)
export interface Citizen {
  id: string
  worldId: string
  householdId: string | null
  name: string
  age: number
  homeBuildingId: string | null
  currentBuildingId: string | null
  employmentStatus: string
  employerId: string | null
  happiness: number
  health: number
  skills: Record<string, unknown>
  riskTolerance: number
  consumptionPreference: number
  currentActivity: string
  currentDestination: string | null
  arrivalTick: number | null
  cashBalance: number | null
}

// Frontend assumption: proposed SSE citizen.movement.started payload (backend undefined)
export interface MovementEventDTO {
  citizen_id: string
  from_building_id: string
  to_building_id: string
  start_tick: number
  arrival_tick: number
}

export interface MovementEvent {
  citizenId: string
  fromBuildingId: string
  toBuildingId: string
  startTick: number
  arrivalTick: number
}

export type Selection = { kind: 'building' | 'citizen'; id: string } | null
