import ReactEChartsCore from 'echarts-for-react/esm/core'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { formatFixed } from '@/lib/format'
import { AXIS_TEXT, COLOURS, echarts, FONT } from './theme'

// A horizontal bar chart that compares the full model with simpler methods on one measure.
// The full model is blue and the other methods are grey, so the eye goes to the full model.
// The value sits at the end of each bar. A dashed line can mark the score of a random guess,
// which is the floor that every method should beat.

export interface ComparisonRow {
  label: string
  value: number
  highlight?: boolean
}

interface Props {
  rows: ComparisonRow[]
  max?: number
  baseline?: { value: number; label: string }
  summary: string
}

const BASELINE_SPACE = 32

export function ComparisonChart({ rows, max, baseline, summary }: Props) {
  const { i18n } = useTranslation()
  const language = i18n.language
  const option = useMemo(
    () => ({
      animation: false,
      textStyle: { fontFamily: FONT },
      grid: {
        left: 8,
        right: 56,
        top: baseline ? BASELINE_SPACE : 8,
        bottom: 8,
        containLabel: true,
      },
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
          markLine: baseline
            ? {
                silent: true,
                symbol: 'none',
                data: [
                  {
                    xAxis: baseline.value,
                    lineStyle: { color: COLOURS.inkSecondary, type: 'dashed', width: 1.5 },
                    // The category axis runs from top to bottom, so the start of the line is
                    // at the top, in the space kept free above the bars.
                    label: {
                      ...AXIS_TEXT,
                      position: 'start',
                      formatter: baseline.label,
                    },
                  },
                ],
              }
            : undefined,
        },
      ],
    }),
    [rows, max, baseline, language],
  )
  return (
    <figure className="m-0">
      <figcaption className="sr-only">{summary}</figcaption>
      <div aria-hidden="true">
        <ReactEChartsCore
          echarts={echarts}
          option={option}
          notMerge
          style={{
            height: rows.length * 40 + 24 + (baseline ? BASELINE_SPACE : 0),
            width: '100%',
          }}
        />
      </div>
    </figure>
  )
}
