import { describe, expect, it } from 'vitest'
import { mulberry32, uuidV4 } from './prng'

describe('prng', () => {
  it('same seed -> same sequence, in [0,1)', () => {
    const a = mulberry32(42)
    const b = mulberry32(42)
    const sa = Array.from({ length: 100 }, () => a())
    expect(sa).toEqual(Array.from({ length: 100 }, () => b()))
    expect(sa.every((v) => v >= 0 && v < 1)).toBe(true)
  })

  it('different seed -> different sequence', () => {
    expect(mulberry32(1)()).not.toBe(mulberry32(2)())
  })

  it('uuidV4 format, deterministic, unique', () => {
    const re = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
    const r = mulberry32(7)
    const ids = Array.from({ length: 500 }, () => uuidV4(r))
    expect(ids.every((u) => re.test(u))).toBe(true)
    expect(new Set(ids).size).toBe(500)
    const r2 = mulberry32(7)
    expect(uuidV4(r2)).toBe(ids[0])
  })
})
