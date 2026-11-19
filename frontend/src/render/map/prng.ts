export function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function uuidV4(rng: () => number): string {
  const b = new Uint8Array(16)
  for (let i = 0; i < 4; i++) {
    const w = Math.floor(rng() * 4294967296) >>> 0
    b[i * 4] = w >>> 24
    b[i * 4 + 1] = (w >>> 16) & 255
    b[i * 4 + 2] = (w >>> 8) & 255
    b[i * 4 + 3] = w & 255
  }
  b[6] = (b[6] & 0x0f) | 0x40
  b[8] = (b[8] & 0x3f) | 0x80
  const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('')
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`
}
