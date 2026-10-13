import ReactEChartsCore from 'echarts-for-react/esm/core'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDate, formatNumber, formatShortDate } from '@/lib/format'
import { AXIS_TEXT, COLOURS, echarts, FONT } from './theme'

// A small bar chart with one bar for each day, for example the steps on each day or the
// hours of sleep on each night. A single series needs no legend, because the title says
// what the chart shows.

interface Props {
  dates: string[]
  values: (number | null)[]
  unit: string
  digits?: number
  height?: number
  summary: string
}

export function DailyBarChart({ dates, values, unit, digits = 0, height = 180, summary }: Props) {
  const { i18n } = useTranslation()
  const language = i18n.language

  const option = useMemo(
    () => ({
      animation: false,
      textStyle: { fontFamily: FONT },
      grid: { left: 64, right: 16, top: 16, bottom: 32 },
      tooltip: {
        trigger: 'item',
        textStyle: { fontFamily: FONT, fontSize: 16, color: COLOURS.ink },
        formatter: (p: { dataIndex: number }) => {
          const value = values[p.dataIndex]
          const text = value == null ? '' : `${formatNumber(value, language, digits)} ${unit}`
          return `<strong>${text}</strong><br/>${formatDate(dates[p.dataIndex], language)}`
        },
      },
      xAxis: {
        type: 'category',
        data: dates.map((d) => formatShortDate(d, language)),
        axisLabel: { ...AXIS_TEXT, hideOverlap: true },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: COLOURS.axis } },
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          ...AXIS_TEXT,
          formatter: (v: number) => formatNumber(v, language),
        },
        splitLine: { lineStyle: { color: COLOURS.grid, width: 1 } },
      },
      series: [
        {
          type: 'bar',
          data: values,
          barMaxWidth: 24,
          itemStyle: { color: COLOURS.measured, borderRadius: [4, 4, 0, 0] },
          emphasis: { itemStyle: { color: '#1c5cab' } },
        },
      ],
    }),
    [dates, values, unit, digits, language],
  )

  return (
    <figure className="m-0">
      <figcaption className="sr-only">{summary}</figcaption>
      <div aria-hidden="true">
        <ReactEChartsCore
          echarts={echarts}
          option={option}
          notMerge
          style={{ height, width: '100%' }}
        />
      </div>
    </figure>
  )
}
