interface DayBucket {
  date: string
  study: number
  habit: number
  milestone: number
}

interface Props {
  days: DayBucket[]
}

// Slot dimensions
const BAR_W = 14
const GAP = 4
const SLOT = BAR_W + GAP
const PAD_X = 8
const CHART_H = 60
const LABEL_H = 18
const SVG_H = CHART_H + LABEL_H

export default function ActivityChart({ days }: Props) {
  const svgW = PAD_X * 2 + days.length * SLOT - GAP
  const maxTotal = Math.max(1, ...days.map(d => d.study + d.habit + d.milestone))

  return (
    <div>
      <svg
        viewBox={`0 0 ${svgW} ${SVG_H}`}
        className="w-full"
        preserveAspectRatio="xMidYMid meet"
        aria-label="Activity last 30 days"
      >
        {days.map((d, i) => {
          const x = PAD_X + i * SLOT
          const total = d.study + d.habit + d.milestone

          // Stack segments bottom-to-top: study, habit, milestone
          const segments: Array<{ count: number; fill: string }> = [
            { count: d.study, fill: '#6366f1' },
            { count: d.habit, fill: '#10b981' },
            { count: d.milestone, fill: '#f59e0b' },
          ]

          let yBottom = CHART_H
          const rects = segments
            .filter(s => s.count > 0)
            .map(s => {
              const h = Math.max(1, (s.count / maxTotal) * CHART_H)
              yBottom -= h
              return { fill: s.fill, y: yBottom, h }
            })

          const showLabel = i % 7 === 0
          const [, mon, day] = d.date.split('-')
          const label = `${parseInt(mon)}/${parseInt(day)}`

          return (
            <g key={d.date}>
              {total === 0 ? (
                <rect x={x} y={CHART_H - 2} width={BAR_W} height={2} fill="#3f3f46" rx={1} />
              ) : (
                rects.map((r, ri) => (
                  <rect key={ri} x={x} y={r.y} width={BAR_W} height={r.h} fill={r.fill} rx={ri === rects.length - 1 ? 2 : 0} />
                ))
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
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-indigo-500" />
          Study
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-emerald-500" />
          Habit
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-amber-500" />
          Milestone
        </span>
      </div>
    </div>
  )
}
