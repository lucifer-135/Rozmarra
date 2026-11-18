import { useEffect, useRef, useState } from 'react'

// ECharts wraps a long legend onto more rows, but it does not move the plot down. The chart
// therefore counts the rows itself and starts the plot below the last one.

/** Counts the rows that entries of these widths fill when each row is `available` pixels wide. */
export function countLegendRows(widths: number[], available: number, gap: number): number {
  let rows = 0
  let used = 0
  for (const width of widths) {
    if (rows === 0 || used + gap + width > available) {
      rows += 1
      used = width
    } else {
      used += gap + width
    }
  }
  return rows
}

let canvas: HTMLCanvasElement | null = null

/** Measures text in the given CSS font, or returns null where the browser cannot measure. */
export function measureText(text: string, font: string): number | null {
  try {
    canvas ??= document.createElement('canvas')
    const context = canvas.getContext('2d')
    if (!context) return null
    context.font = font
    return context.measureText(text).width
  } catch {
    // The test browser (jsdom) has no canvas. The caller then keeps its fixed legend height.
    return null
  }
}

/** Follows the width of an element, which is 0 until the element is on the page. */
export function useElementWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return [ref, width] as const
}
