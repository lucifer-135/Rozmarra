import ReactEChartsCore from 'echarts-for-react/esm/core'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { formatFixed } from '@/lib/format'
import { AXIS_TEXT, COLOURS, echarts, FONT } from './theme'

// A horizontal bar chart that compares the full model with simpler methods on one measure.
// The full model is blue and the other methods are grey, so the eye goes to the full model.
// The value sits at the end of each bar.

export interface ComparisonRow {
  label: string
  value: number
  highlight?: boolean
}

interface Props {
  rows: ComparisonRow[]
  max?: number
  summary: string
}

export function ComparisonChart({ rows, max, summary }: Props) {
  const { i18n } = useTranslation()
  const language = i18n.language
  const option = useMemo(
    () => ({
      animation: false,
      textStyle: { fontFamily: FONT },
      grid: { left: 8, right: 56, top: 8, bottom: 8, containLabel: true },
      xAxis: { type: 'value', min: 0, max: max ?? Math.max(...rows.map((r) => r.value)) * 1.15, show: false },
      yAxis: {
        type: 'category',
        inverse: true,
        data: rows.map((r) => r.label),
        axisLabel: { ...AXIS_TEXT, color: COLOURS.ink },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: COLOURS.axis } },
      },
      series: [
        {
          type: 'bar',
          barMaxWidth: 22,
          data: rows.map((r) => ({
            value: r.value,
            itemStyle: {
              color: r.highlight ? COLOURS.measured : '#b4b2ab',
              borderRadius: [0, 4, 4, 0],
            },
          })),
          label: {
            show: true,
            position: 'right',
            ...AXIS_TEXT,
            color: COLOURS.ink,
            formatter: (p: { value: number }) => formatFixed(p.value, language, 3),
          },
        },
      ],
    }),
    [rows, max, language],
  )
  return (
    <figure className="m-0">
      <figcaption className="sr-only">{summary}</figcaption>
      <div aria-hidden="true">
        <ReactEChartsCore
          echarts={echarts}
          option={option}
          notMerge
          style={{ height: rows.length * 40 + 24, width: '100%' }}
        />
      </div>
    </figure>
  )
}
