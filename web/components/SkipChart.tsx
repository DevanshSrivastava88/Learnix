interface DayBucket {
  date: string
  skips: number
}

interface Props {
  days: DayBucket[]
  totalSkips: number
}

const BAR_W = 14
const GAP = 4
const SLOT = BAR_W + GAP
const PAD_X = 8
const CHART_H = 60
const LABEL_H = 18
const SVG_H = CHART_H + LABEL_H

export default function SkipChart({ days, totalSkips }: Props) {
  const svgW = PAD_X * 2 + days.length * SLOT - GAP
  const maxSkips = Math.max(1, ...days.map(d => d.skips))

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-zinc-500">Skips per day</span>
        <span className="text-xs text-zinc-400 font-medium">
          {totalSkips} total skip{totalSkips !== 1 ? 's' : ''}
        </span>
      </div>

      <svg
        viewBox={`0 0 ${svgW} ${SVG_H}`}
        className="w-full"
        preserveAspectRatio="xMidYMid meet"
        aria-label="Skips last 30 days"
      >
        {days.map((d, i) => {
          const x = PAD_X + i * SLOT
          const isHighest = d.skips > 0 && d.skips === maxSkips
          const fill = isHighest ? '#ef4444' : '#f87171'
          const h = d.skips > 0 ? Math.max(2, (d.skips / maxSkips) * CHART_H) : 0

          const showLabel = i % 7 === 0
          const [, mon, day] = d.date.split('-')
          const label = `${parseInt(mon)}/${parseInt(day)}`

          return (
            <g key={d.date}>
              {d.skips === 0 ? (
                <rect x={x} y={CHART_H - 2} width={BAR_W} height={2} fill="#3f3f46" rx={1} />
              ) : (
                <rect
                  x={x}
                  y={CHART_H - h}
                  width={BAR_W}
                  height={h}
                  fill={fill}
                  rx={2}
                />
              )}
              {showLabel && (
                <text
                  x={x + BAR_W / 2}
                  y={SVG_H - 3}
                  textAnchor="middle"
                  fontSize="8"
                  fill="#71717a"
                >
                  {label}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      <div className="flex gap-4 mt-2 text-xs text-zinc-500">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-red-500" />
          Skips
          <span className="text-zinc-600 ml-1">(peak day highlighted)</span>
        </span>
      </div>
    </div>
  )
}
