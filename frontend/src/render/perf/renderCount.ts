const counts: Record<string, number> = {}

// DEV only: counts React renders per component (read by CDP checks via renderCounts()).
export function useRenderCount(name: string): void {
  if (import.meta.env.DEV) counts[name] = (counts[name] ?? 0) + 1
}

export function renderCounts(): Record<string, number> {
  return { ...counts }
}
