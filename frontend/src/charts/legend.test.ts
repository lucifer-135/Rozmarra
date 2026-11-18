import { describe, expect, it } from 'vitest'
import { countLegendRows } from './legend'

describe('countLegendRows', () => {
  it('keeps every entry on one row when they fit', () => {
    expect(countLegendRows([100, 100, 100], 400, 20)).toBe(1)
  })

  it('moves an entry to the next row when it does not fit', () => {
    // 100 + 20 + 100 + 20 + 100 = 340, which is wider than 300.
    expect(countLegendRows([100, 100, 100], 300, 20)).toBe(2)
  })

  it('counts three rows for a narrow chart', () => {
    expect(countLegendRows([180, 170, 180, 170, 230], 420, 20)).toBe(3)
  })

  it('gives one row to an entry wider than the chart', () => {
    expect(countLegendRows([500, 100], 300, 20)).toBe(2)
  })

  it('counts no rows for an empty legend', () => {
    expect(countLegendRows([], 300, 20)).toBe(0)
  })
})
