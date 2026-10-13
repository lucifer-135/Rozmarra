import ReactEChartsCore from 'echarts-for-react/esm/core'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { formatAxisTime, formatNumber, formatShortDate, formatTime, toDate } from '@/lib/format'
import { AXIS_TEXT, COLOURS, echarts, FONT } from './theme'

// A small line chart for one wearable signal, such as the heart rate, on the same kind of
// time axis as the glucose chart.

interface Props {
  times: string[]
  values: (number | null)[]
  unit: string
  start?: string
  end?: string
  multiDay?: boolean
  height?: number
  summary: string
}

export function SignalChart({
  times,
  values,
  unit,
  start,
  end,
  multiDay = false,
  height = 180,
  summary,
}: Props) {
  const { i18n } = useTranslation()
  const language = i18n.language

  const option = useMemo(() => {
    const data = times.map((t, i) => [toDate(t).getTime(), values[i] ?? null])
    return {
      animation: false,
      textStyle: { fontFamily: FONT },
      grid: { left: 64, right: 16, top: 16, bottom: 32 },
      tooltip: {
        trigger: 'axis',
        textStyle: { fontFamily: FONT, fontSize: 16, color: COLOURS.ink },
        formatter: (params: { value: [number, number | null] }[]) => {
          const [time, value] = params[0]?.value ?? []
          if (value == null) return ''
          return `<strong>${formatNumber(value, language)} ${unit}</strong><br/>${formatTime(
            time,
            language,
          )}`
        },
      },
      xAxis: {
        type: 'time',
        min: start ? toDate(start).getTime() : undefined,
        max: end ? toDate(end).getTime() : undefined,
        axisLine: { lineStyle: { color: COLOURS.axis } },
        splitLine: { show: true, lineStyle: { color: COLOURS.grid, width: 1 } },
        axisLabel: {
          ...AXIS_TEXT,
          hideOverlap: true,
          formatter: (value: number) =>
            multiDay ? formatShortDate(value, language) : formatAxisTime(value, language),
        },
        ...(multiDay ? { minInterval: 86_400_000, maxInterval: 86_400_000 } : {}),
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLabel: AXIS_TEXT,
        splitLine: { lineStyle: { color: COLOURS.grid, width: 1 } },
      },
      series: [
        {
          type: 'line',
          data,
          symbol: 'none',
          lineStyle: { color: COLOURS.measured, width: 1.5 },
          itemStyle: { color: COLOURS.measured },
        },
      ],
    }
  }, [times, values, unit, start, end, multiDay, language])

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
