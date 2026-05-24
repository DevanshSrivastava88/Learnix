import { supabase } from '@/lib/supabase'
import { Goal, Topic } from '@/lib/types'
import { buildTopicTree, daysUntil, formatDate, countCompleted } from '@/lib/utils'
import { notFound } from 'next/navigation'
import GoalDetailClient from './GoalDetailClient'

export const revalidate = 0

interface Props {
  params: { id: string }
}

async function getGoalData(id: string) {
  const [goalRes, topicsRes] = await Promise.all([
    supabase.from('goals').select('*').eq('id', id).single(),
    supabase
      .from('topics')
      .select('*')
      .eq('goal_id', id)
      .order('order_index', { ascending: true }),
  ])

  if (goalRes.error || !goalRes.data) return null

  return {
    goal: goalRes.data as Goal,
    topics: (topicsRes.data ?? []) as Topic[],
  }
}

export default async function GoalDetailPage({ params }: Props) {
  const data = await getGoalData(params.id)
  if (!data) notFound()

  const { goal, topics } = data
  const tree = buildTopicTree(topics)
  const total = topics.length
  const done = countCompleted(topics)
  const pct = total > 0 ? Math.round((done / total) * 100) : 0
  const days = daysUntil(goal.target_date)

  return (
    <div className="p-6 md:p-8 max-w-4xl mx-auto">
      {/* Goal header */}
      <div className="mb-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-zinc-100">{goal.name}</h1>
            {goal.description && (
              <p className="text-sm text-zinc-500 mt-1">{goal.description}</p>
            )}
          </div>
          <div className="text-right shrink-0">
            {goal.target_date && (
              <p className="text-sm text-zinc-400">{formatDate(goal.target_date)}</p>
            )}
            {days !== null && (
              <p
                className={`text-xs mt-0.5 font-medium ${
                  days < 0
                    ? 'text-red-400'
                    : days === 0
                    ? 'text-orange-400'
                    : 'text-zinc-500'
                }`}
              >
                {days < 0
                  ? `${Math.abs(days)}d overdue`
                  : days === 0
                  ? 'Due today'
                  : `${days}d left`}
              </p>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div className="mt-5">
          <div className="flex justify-between text-xs text-zinc-500 mb-1.5">
            <span>{done}/{total} topics done</span>
            <span>{pct}%</span>
          </div>
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-500 rounded-full transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Topic tree + panel — client component */}
      <GoalDetailClient
        goalId={goal.id}
        topicTree={tree}
        allTopics={topics}
      />
    </div>
  )
}
