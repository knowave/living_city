import type { Speed } from './SimClock'

export const COUNTS: readonly number[] = [0, 100, 500, 1000]
const SPEEDS: readonly Speed[] = [1, 4, 16]

export function parseCount(raw: string | null): number {
  const n = Number(raw)
  return raw !== null && COUNTS.includes(n) ? n : 100
}

interface Props {
  count: number
  speed: Speed
  onCount: (n: number) => void
  onSpeed: (s: Speed) => void
}

const btn = (on: boolean) => `rounded px-2 py-0.5 ${on ? 'bg-white text-black' : 'bg-white/20'}`

export function CitizenControls({ count, speed, onCount, onSpeed }: Props) {
  const pickCount = (n: number) => {
    onCount(n)
    const u = new URL(location.href)
    u.searchParams.set('citizens', String(n))
    history.replaceState(null, '', u)
  }
  return (
    <div className="absolute bottom-2 left-2 flex flex-col gap-1 rounded bg-black/60 px-2 py-1 font-mono text-xs text-white">
      <div className="flex gap-1">
        {COUNTS.map((n) => (
          <button key={n} type="button" className={btn(n === count)} onClick={() => pickCount(n)}>
            {n}
          </button>
        ))}
      </div>
      <div className="flex gap-1">
        {SPEEDS.map((s) => (
          <button key={s} type="button" className={btn(s === speed)} onClick={() => onSpeed(s)}>
            {s}×
          </button>
        ))}
      </div>
    </div>
  )
}
