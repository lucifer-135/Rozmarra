import ReactEChartsCore from 'echarts-for-react/esm/core'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { formatAxisTime, formatNumber, formatTime, toDate } from '@/lib/format'
import { AXIS_TEXT, COLOURS, echarts, FONT } from './theme'

// The alert timeline of the live fasting monitor: the estimated chance of low glucose within
// the next 60 minutes, the alert level and the alerts so far. A single series needs no
// legend, because the heading says what the chart shows.

interface Props {
  times: string[]
  chances: (number | null)[]
  threshold: number
  alerts: string[]
  now: string
  start: string
  end: string
  height?: number
  summary: string
}

export function ChanceChart({
  times,
  chances,
  threshold,
  alerts,
  now,
  start,
  end,
  height = 200,
  summary,
}: Props) {
  const { t, i18n } = useTranslation()
  const language = i18n.language

  const option = useMemo(() => {
    const ms = (value: string) => toDate(value).getTime()
    const percent = (v: number | null) => (v == null ? null : Math.round(v * 1000) / 10)
    const highest = Math.max(threshold * 100 * 2, ...chances.map((v) => (v ?? 0) * 100))
    const alertSet = new Set(alerts)
    return {
      animation: false,
      textStyle: { fontFamily: FONT },
      grid: { left: 64, right: 24, top: 24, bottom: 36 },
      tooltip: {
        trigger: 'axis',
        textStyle: { fontFamily: FONT, fontSize: 16, color: COLOURS.ink },
        formatter: (params: { value: [number, number | null] }[]) => {
          const [time, value] = params[0]?.value ?? []
          if (value == null) return ''
          return `<strong>${formatNumber(value, language, 1)}%</strong><br/>${formatTime(time, language)}`
        },
      },
      xAxis: {
        type: 'time',
        min: ms(start),
        max: ms(end),
        axisLine: { lineStyle: { color: COLOURS.axis } },
        splitLine: { show: true, lineStyle: { color: COLOURS.grid, width: 1 } },
        axisLabel: {
          ...AXIS_TEXT,
          hideOverlap: true,
          formatter: (value: number) => formatAxisTime(value, language),
        },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: Math.ceil(highest / 5) * 5,
        name: '%',
        nameTextStyle: { ...AXIS_TEXT, align: 'right' },
        axisLabel: AXIS_TEXT,
        splitLine: { lineStyle: { color: COLOURS.grid, width: 1 } },
      },
      series: [
        {
          type: 'line',
          data: times.map((time, i) => [ms(time), percent(chances[i])]),
          symbol: 'none',
          lineStyle: { color: COLOURS.measured, width: 2 },
          itemStyle: { color: COLOURS.measured },
          markLine: {
            silent: true,
            symbol: 'none',
            data: [
              {
                yAxis: Math.round(threshold * 1000) / 10,
                lineStyle: { color: COLOURS.low, type: 'dashed', width: 1.5 },
                label: {
                  ...AXIS_TEXT,
                  color: COLOURS.low,
                  position: 'insideEndTop',
                  formatter: t('monitor.alertLevel', {
                    value: formatNumber(threshold * 100, language, 1),
                  }),
                },
              },
              {
                xAxis: ms(now),
                lineStyle: { color: COLOURS.ink, type: 'solid', width: 1.5 },
                label: { ...AXIS_TEXT, color: COLOURS.ink, formatter: t('monitor.now') },
              },
            ],
          },
          markPoint: {
            symbol: 'triangle',
            symbolSize: 14,
            itemStyle: { color: COLOURS.low, borderColor: COLOURS.surface, borderWidth: 2 },
            label: { show: false },
            data: times
              .map((time, i) => ({ time, value: percent(chances[i]) }))
              .filter((p) => alertSet.has(p.time))
              .map((p) => ({ coord: [ms(p.time), p.value] })),
          },
        },
      ],
    }
  }, [times, chances, threshold, alerts, now, start, end, language, t])

  return (
    <figure className="m-0">
      <figcaption className="sr-only">{summary}</figcaption>
      <div aria-hidden="true">
        <ReactEChartsCore echarts={echarts} option={option} notMerge style={{ height, width: '100%' }} />
      </div>
    </figure>
  )
}
