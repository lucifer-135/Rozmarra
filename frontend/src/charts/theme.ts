// Colours for the charts. The two plan colours are the first two slots of a categorical
// palette that passes checks for colour vision deficiency. Every colour on a chart also has
// a text label, a line style or an icon, so the charts do not rely on colour alone.

import * as echarts from 'echarts/core'
import { BarChart, LineChart, ScatterChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  LineChart,
  ScatterChart,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
  CanvasRenderer,
])

export { echarts }

export const COLOURS = {
  planA: '#2a78d6',
  planB: '#eb6834',
  measured: '#2a78d6',
  average: '#6b6a65',
  meal: '#1baf7a',
  medicine: '#4a3aa7',
  activity: '#c98500',
  low: '#d03b3b',
  veryLow: '#8f1d1d',
  targetRange: 'rgba(12, 163, 12, 0.07)',
  fastWindow: 'rgba(137, 135, 129, 0.12)',
  ink: '#0b0b0b',
  inkSecondary: '#52514e',
  muted: '#6b6a65',
  grid: '#e1e0d9',
  axis: '#c3c2b7',
  surface: '#ffffff',
} as const

export const FONT = "'Noto Sans', 'Noto Sans Devanagari', sans-serif"

// Text on the charts is 16 pixels, the minimum text size in the dashboard.
export const AXIS_TEXT = { color: COLOURS.inkSecondary, fontSize: 16, fontFamily: FONT }
