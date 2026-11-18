export interface FpsStats {
  fps: number
  avg: number
}

const WINDOW_SEC = 1
const REPORT_EVERY_SEC = 0.5

export function createFpsTracker() {
  let start: number | null = null
  let last = 0
  let frames = 0
  let recent: number[] = []

  return {
    tick(nowSec: number): FpsStats | null {
      if (start === null) {
        start = nowSec
        last = nowSec
      }
      frames++
      recent.push(nowSec)
      recent = recent.filter((t) => t > nowSec - WINDOW_SEC)

      if (nowSec - last < REPORT_EVERY_SEC) return null
      last = nowSec

      const span = recent[recent.length - 1] - recent[0]
      const fps = recent.length > 1 && span > 0 ? (recent.length - 1) / span : 0
      const avg = (frames - 1) / (nowSec - start)
      return { fps, avg }
    },
  }
}
