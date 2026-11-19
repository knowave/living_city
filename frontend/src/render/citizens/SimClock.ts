// TBD, mock-only: real tick duration is owned by the Python engine (Phase 4~5).
export const MOCK_TICK_SECONDS = 10

export type Speed = 1 | 4 | 16

// Fractional tick derived from wall time, so hidden tabs / off-screen citizens stay continuous.
export class SimClock {
  private baseTick = 0
  private t0: number
  private _speed: Speed

  constructor(nowMs: number, speed: Speed = 1) {
    this.t0 = nowMs
    this._speed = speed
  }

  tickAt(nowMs: number): number {
    return this.baseTick + ((nowMs - this.t0) / 1000 / MOCK_TICK_SECONDS) * this._speed
  }

  setSpeed(speed: Speed, nowMs: number): void {
    this.baseTick = this.tickAt(nowMs)
    this.t0 = nowMs
    this._speed = speed
  }

  get speed(): Speed {
    return this._speed
  }
}
