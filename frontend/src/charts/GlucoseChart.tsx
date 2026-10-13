import ReactEChartsCore from 'echarts-for-react/esm/core'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { formatAxisTime, formatShortDate, formatTime, toDate } from '@/lib/format'
import { glucoseAxisTop, Y_MIN, Y_STEP } from './scale'
import { AXIS_TEXT, COLOURS, echarts, FONT } from './theme'

// The main glucose chart (docs/techstack.md, Section 11.2): the target range from 70 to
// 180 mg/dL, labelled lines at 70 and 54 mg/dL, the glucose lines with an optional band,
// the fasting window, and a strip below the chart with the meals, medicines and activities.

export interface GlucoseLine {
  id: string
  name: string
  times: string[]
  values: (number | null)[]
  colour: string
  style: 'solid' | 'dashed' | 'dotted'
  band?: { name: string; lower: (number | null)[]; upper: (number | null)[] }
  // The lowest point to label. When it is not given, the chart labels the lowest value it draws.
  lowest?: { value: number; time: string }
  labelLowest?: boolean
}

export interface ChartEvent {
  kind: 'meal' | 'medicine' | 'activity'
  start: string
  end?: string
  label: string
  short?: string
}

export interface ChartWindow {
  start: string
  end: string
  label: string
}

/** A vertical line at one moment, for example "Now" in the live fasting monitor. */
export interface ChartMoment {
  time: string
  label: string
}

interface Props {
  lines: GlucoseLine[]
  events?: ChartEvent[]
  windows?: ChartWindow[]
  moments?: ChartMoment[]
  start?: string
  end?: string
  yMax?: number
  height?: number
  multiDay?: boolean
  summary: string
}

const STRIP_ROW = 30

function escapeHtml(text: string): string {
  return text.replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] ?? c,
  )
}

const ms = (value: string) => toDate(value).getTime()
const TARGET_KEY = 'rgba(12, 163, 12, 0.25)'

function pairs(times: string[], values: (number | null)[]) {
  return times.map((t, i) => [ms(t), values[i] ?? null])
}

function nearestIndex(times: number[], target: number): number {
  let best = 0
  for (let i = 1; i < times.length; i++) {
    if (Math.abs(times[i] - target) < Math.abs(times[best] - target)) best = i
  }
  return best
}

export function GlucoseChart({
  lines,
  events = [],
  windows = [],
  moments = [],
  start,
  end,
  yMax,
  height = 320,
  multiDay = false,
  summary,
}: Props) {
  const { t, i18n } = useTranslation()
  // With a "Now" line, the forecast fills the right side, so the limit labels move to the left.
  const lowPosition = moments.length ? 'insideStartTop' : 'insideEndTop'
  const veryLowPosition = moments.length ? 'insideStartBottom' : 'insideEndBottom'
  const language = i18n.language

  const option = useMemo(() => {
    const allTimes = lines.flatMap((l) => l.times.map(ms))
    const xMin = start ? ms(start) : Math.min(...allTimes)
    const xMax = end ? ms(end) : Math.max(...allTimes)
    const highest = Math.max(
      0,
      ...lines.flatMap((l) => [...l.values, ...(l.band?.upper ?? [])]).map((v) => v ?? 0),
    )
    const top = yMax ?? glucoseAxisTop(highest)

    const kinds = (['meal', 'medicine', 'activity'] as const).filter((k) =>
      events.some((e) => e.kind === k),
    )
    const stripRows = kinds.map((k) => t(`chart.strip.${k}`))
    const stripHeight = stripRows.length * STRIP_ROW
    const hasStrip = stripRows.length > 0
    const mainBottom = hasStrip ? stripHeight + 72 : 40

    const xAxisBase = {
      type: 'time' as const,
      min: xMin,
      max: xMax,
      axisLine: { lineStyle: { color: COLOURS.axis } },
      splitLine: { show: true, lineStyle: { color: COLOURS.grid, width: 1 } },
      axisLabel: {
        ...AXIS_TEXT,
        hideOverlap: true,
        formatter: (value: number) =>
          multiDay ? formatShortDate(value, language) : formatAxisTime(value, language),
      },
      ...(multiDay ? { minInterval: 86_400_000, maxInterval: 86_400_000 } : {}),
    }

    // Each line may have a band, drawn as a stacked area from the lower to the upper value.
    const series: Record<string, unknown>[] = []
    const legend: (string | { name: string; icon: string })[] = []
    for (const line of lines) {
      if (line.band) {
        const lower = line.band.lower
        const spread = line.band.upper.map((u, i) =>
          u == null || lower[i] == null ? null : u - (lower[i] as number),
        )
        series.push({
          id: `${line.id}-band-lower`,
          type: 'line',
          data: pairs(line.times, lower),
          stack: `${line.id}-band`,
          symbol: 'none',
          lineStyle: { opacity: 0 },
          silent: true,
          z: 1,
        })
        series.push({
          id: `${line.id}-band`,
          name: line.band.name,
          type: 'line',
          data: pairs(line.times, spread),
          stack: `${line.id}-band`,
          symbol: 'none',
          lineStyle: { opacity: 0 },
          areaStyle: { color: line.colour, opacity: 0.14 },
          itemStyle: { color: line.colour, opacity: 0.35 },
          silent: true,
          z: 1,
        })
        legend.push({ name: line.band.name, icon: 'roundRect' })
      }
      const values = line.values.map((v) => v ?? Infinity)
      const index = values.indexOf(Math.min(...values))
      const lowest =
        line.lowest ??
        (index >= 0 && Number.isFinite(values[index])
          ? { value: values[index], time: line.times[index] }
          : null)
      series.push({
        id: line.id,
        name: line.name,
        type: 'line',
        data: pairs(line.times, line.values),
        symbol: 'none',
        showSymbol: false,
        connectNulls: false,
        lineStyle: {
          color: line.colour,
          width: line.style === 'dotted' ? 2.5 : 2,
          type: line.style,
          cap: 'round',
          join: 'round',
        },
        itemStyle: { color: line.colour },
        z: line.style === 'dotted' ? 2 : 3,
        markPoint:
          line.labelLowest && lowest
            ? {
                symbol: 'circle',
                symbolSize: 10,
                itemStyle: { color: line.colour, borderColor: COLOURS.surface, borderWidth: 2 },
                label: {
                  ...AXIS_TEXT,
                  color: COLOURS.ink,
                  position: 'bottom',
                  distance: 8,
                  formatter: () =>
                    t('chart.lowestLabel', {
                      value: Math.round(lowest.value),
                      time: formatTime(lowest.time, language),
                    }),
                },
                data: [{ coord: [ms(lowest.time), lowest.value] }],
              }
            : undefined,
      })
      legend.push(line.name)
    }

    // The target range appears in the legend, so that no label sits behind the glucose line.
    series.push({
      id: 'target-legend',
      name: t('chart.targetRangeLegend'),
      type: 'line',
      data: [],
      symbol: 'none',
      lineStyle: { opacity: 0 },
      areaStyle: { color: TARGET_KEY },
      itemStyle: { color: TARGET_KEY },
    })
    legend.push({ name: t('chart.targetRangeLegend'), icon: 'roundRect' })

    // A helper series carries the target range, the low glucose lines and the fasting window,
    // so that they stay visible when a reader hides a line in the legend.
    series.push({
      id: 'reference',
      type: 'line',
      data: [
        [xMin, null],
        [xMax, null],
      ],
      silent: true,
      symbol: 'none',
      markArea: {
        silent: true,
        data: [
          [
            { yAxis: 70, itemStyle: { color: COLOURS.targetRange }, label: { show: false } },
            { yAxis: 180 },
          ],
          ...windows.map((w) => [
            {
              xAxis: ms(w.start),
              itemStyle: { color: COLOURS.fastWindow },
              label: { ...AXIS_TEXT, position: 'insideTop', formatter: w.label },
            },
            { xAxis: ms(w.end) },
          ]),
        ],
      },
      markLine: {
        silent: true,
        symbol: 'none',
        data: [
          {
            yAxis: 70,
            lineStyle: { color: COLOURS.low, type: 'dashed', width: 1.5 },
            label: {
              ...AXIS_TEXT,
              color: COLOURS.low,
              position: lowPosition,
              formatter: t('chart.lowLine'),
            },
          },
          {
            yAxis: 54,
            lineStyle: { color: COLOURS.veryLow, type: 'dashed', width: 1.5 },
            label: {
              ...AXIS_TEXT,
              color: COLOURS.veryLow,
              position: veryLowPosition,
              formatter: t('chart.veryLowLine'),
            },
          },
          ...moments.map((m) => ({
            xAxis: ms(m.time),
            lineStyle: { color: COLOURS.ink, type: 'solid', width: 1.5 },
            label: { ...AXIS_TEXT, color: COLOURS.ink, position: 'end', formatter: m.label },
          })),
        ],
      },
    })

    // The strip of meals, medicines and activities below the chart.
    const row = (kind: ChartEvent['kind']) => t(`chart.strip.${kind}`)
    for (const kind of kinds) {
      const items = events.filter((e) => e.kind === kind)
      if (kind === 'activity') {
        items.forEach((e, i) =>
          series.push({
            id: `activity-${i}`,
            type: 'line',
            xAxisIndex: 1,
            yAxisIndex: 1,
            data: [
              [ms(e.start), row(kind)],
              [ms(e.end ?? e.start), row(kind)],
            ],
            symbol: 'none',
            lineStyle: { color: COLOURS.activity, width: 10, cap: 'round' },
            silent: true,
          }),
        )
        continue
      }
      // Events at the same time share one marker, with one label.
      const grouped = new Map<number, ChartEvent[]>()
      for (const e of items) grouped.set(ms(e.start), [...(grouped.get(ms(e.start)) ?? []), e])
      series.push({
        id: `strip-${kind}`,
        type: 'scatter',
        xAxisIndex: 1,
        yAxisIndex: 1,
        symbol: kind === 'meal' ? 'circle' : 'diamond',
        symbolSize: 14,
        itemStyle: {
          color: kind === 'meal' ? COLOURS.meal : COLOURS.medicine,
          borderColor: COLOURS.surface,
          borderWidth: 2,
        },
        label: {
          show: kind === 'meal',
          position: 'right',
          ...AXIS_TEXT,
          color: COLOURS.ink,
          formatter: (p: { dataIndex: number }) => {
            const group = [...grouped.values()][p.dataIndex]
            const first = group[0].short ?? group[0].label
            return group.length === 1 ? first : t('chart.andMore', { first, count: group.length - 1 })
          },
        },
        labelLayout: { hideOverlap: true },
        data: [...grouped.keys()].map((time) => ({
          value: [time, row(kind)],
          label: { position: time > xMin + 0.75 * (xMax - xMin) ? 'left' : 'right' },
        })),
        silent: true,
      })
    }

    const lineTimes = lines.map((l) => l.times.map(ms))
    const tooltipFormatter = (params: unknown) => {
      const list = Array.isArray(params) ? params : [params]
      const pointer = (list[0] as { axisValue?: number })?.axisValue
      if (pointer == null) return ''
      const rows = [`<strong>${escapeHtml(formatTime(pointer, language))}</strong>`]
      lines.forEach((line, k) => {
        if (!line.times.length) return
        const i = nearestIndex(lineTimes[k], pointer)
        if (Math.abs(lineTimes[k][i] - pointer) > 16 * 60_000) return
        const value = line.values[i]
        if (value == null) return
        const band =
          line.band && line.band.lower[i] != null && line.band.upper[i] != null
            ? ` <span style="color:${COLOURS.inkSecondary}">(${Math.round(
                line.band.lower[i] as number,
              )} to ${Math.round(line.band.upper[i] as number)})</span>`
            : ''
        const key = `<span style="display:inline-block;width:14px;height:0;border-top:2px ${line.style} ${line.colour};margin-right:6px;vertical-align:middle"></span>`
        rows.push(
          `${key}<strong>${Math.round(value)} mg/dL</strong>${band} ${escapeHtml(line.name)}`,
        )
      })
      for (const e of events) {
        const from = ms(e.start)
        const to = ms(e.end ?? e.start)
        if (pointer >= from - 8 * 60_000 && pointer <= to + 8 * 60_000) {
          rows.push(`${escapeHtml(row(e.kind))}: ${escapeHtml(e.label)}`)
        }
      }
      return rows.join('<br/>')
    }

    // A long legend wraps onto a second line, so the plot starts lower.
    const mainTop = legend.length > 3 ? 76 : 48
    return {
      animation: false,
      textStyle: { fontFamily: FONT },
      grid: [
        { left: 64, right: 24, top: mainTop, bottom: mainBottom },
        ...(hasStrip ? [{ left: 64, right: 24, height: stripHeight, bottom: 36 }] : []),
      ],
      legend: {
        data: legend,
        top: 0,
        left: 96,
        right: 16,
        itemWidth: 28,
        itemGap: 20,
        textStyle: { ...AXIS_TEXT, color: COLOURS.ink },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'line', lineStyle: { color: COLOURS.muted } },
        textStyle: { fontFamily: FONT, fontSize: 16, color: COLOURS.ink },
        formatter: tooltipFormatter,
      },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      xAxis: [
        { ...xAxisBase, axisLabel: { ...xAxisBase.axisLabel, show: !hasStrip } },
        ...(hasStrip ? [{ ...xAxisBase, gridIndex: 1, splitLine: { show: false } }] : []),
      ],
      yAxis: [
        {
          type: 'value',
          min: Y_MIN,
          max: top,
          interval: Y_STEP * Math.max(1, Math.round(top / 300)),
          name: 'mg/dL',
          nameGap: 14,
          nameTextStyle: { ...AXIS_TEXT, align: 'right', padding: [0, 6, 0, 0] },
          axisLabel: AXIS_TEXT,
          splitLine: { lineStyle: { color: COLOURS.grid, width: 1 } },
        },
        ...(hasStrip
          ? [
              {
                type: 'category',
                gridIndex: 1,
                data: stripRows,
                inverse: true,
                axisLabel: { ...AXIS_TEXT, color: COLOURS.ink },
                axisTick: { show: false },
                axisLine: { show: false },
                splitLine: { show: true, lineStyle: { color: COLOURS.grid } },
              },
            ]
          : []),
      ],
      series,
    }
  }, [lines, events, windows, moments, start, end, yMax, multiDay, language, t])

  const stripRows = new Set(events.map((e) => e.kind)).size
  const totalHeight = height + (stripRows ? stripRows * STRIP_ROW + 40 : 0)

  return (
    <figure className="m-0">
      <figcaption className="sr-only">{summary}</figcaption>
      <div aria-hidden="true">
        <ReactEChartsCore
          echarts={echarts}
          option={option}
          notMerge
          lazyUpdate
          style={{ height: totalHeight, width: '100%' }}
        />
      </div>
    </figure>
  )
}
