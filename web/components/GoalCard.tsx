'use client'

import Link from 'next/link'
import { Goal } from '@/lib/types'
import { daysUntil, formatDate } from '@/lib/utils'

interface Props {
  goal: Goal
}

export default function GoalCard({ goal }: Props) {
  const total = goal.topic_count ?? 0
  const done = goal.completed_topic_count ?? 0
  const pct = total > 0 ? Math.round((done / total) * 100) : 0
  const days = daysUntil(goal.target_date)

  let deadlineText = ''
  let deadlineClass = 'text-zinc-500'
  if (days === null) {
    deadlineText = 'No deadline'
  } else if (days < 0) {
    deadlineText = `${Math.abs(days)}d overdue`
    deadlineClass = 'text-red-400'
  } else if (days === 0) {
    deadlineText = 'Due today'
    deadlineClass = 'text-orange-400'
  } else {
    deadlineText = `${days}d left`
    deadlineClass = 'text-zinc-400'
  }

  const statusBadge =
    goal.status === 'completed'
      ? 'bg-green-900 text-green-300'
      : goal.status === 'abandoned'
      ? 'bg-zinc-700 text-zinc-400'
      : 'bg-indigo-900 text-indigo-300'

  const statusLabel =
    goal.status === 'completed'
      ? 'Completed'
      : goal.status === 'abandoned'
      ? 'Abandoned'
      : 'Active'

  return (
    <Link
      href={`/goals/${goal.id}`}
      className="block bg-zinc-800/60 border border-zinc-700 rounded-xl p-5 hover:border-zinc-500 transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="font-semibold text-zinc-100 leading-snug">{goal.name}</p>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${statusBadge}`}>
          {statusLabel}
        </span>
      </div>

      {goal.description && (
        <p className="text-sm text-zinc-500 mt-1 line-clamp-2">{goal.description}</p>
      )}

      <div className="flex items-center gap-3 mt-3">
        <span className={`text-xs font-medium ${deadlineClass}`}>{deadlineText}</span>
        {goal.target_date && (
          <span className="text-zinc-600 text-xs">· {formatDate(goal.target_date)}</span>
        )}
      </div>

      {/* Progress */}
      <div className="mt-4">
        <div className="flex justify-between text-xs text-zinc-500 mb-1.5">
          <span>{done}/{total} topics done</span>
          <span>{pct}%</span>
        </div>
        <div className="h-1.5 bg-zinc-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-indigo-500 rounded-full transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </Link>
  )
}
