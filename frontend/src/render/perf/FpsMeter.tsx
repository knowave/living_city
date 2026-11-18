import { useFrame } from '@react-three/fiber'
import { useMemo } from 'react'
import { createFpsTracker, type FpsStats } from './fps'

export function FpsMeter({ onUpdate }: { onUpdate: (s: FpsStats) => void }) {
  const tracker = useMemo(() => createFpsTracker(), [])

  useFrame(() => {
    const stats = tracker.tick(performance.now() / 1000)
    if (stats) onUpdate(stats)
  })

  return null
}
