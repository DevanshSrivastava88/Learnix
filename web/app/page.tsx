import { supabase } from '@/lib/supabase'
import { Goal, Topic, QuizAttempt, Settings, ActivityLog, TaskSkip } from '@/lib/types'
import { daysUntil, formatDate, statusIcon, countCompleted } from '@/lib/utils'
import Link from 'next/link'
import ActivityChart from '@/components/ActivityChart'
import SkipChart from '@/components/SkipChart'

export const revalidate = 60

function buildSkipBuckets(skips: TaskSkip[]) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const buckets = Array.from({ length: 30 }, (_, i) => {
    const d = new Date(today)
    d.setDate(d.getDate() - (29 - i))
    return { date: d.toISOString().split('T')[0], skips: 0 }
  })

  const idx = new Map(buckets.map((b, i) => [b.date, i]))
  for (const skip of skips) {
    const date = skip.skipped_at.slice(0, 10)
    const i = idx.get(date)
    if (i !== undefined) buckets[i].skips++
  }
  return buckets
}

function buildActivityBuckets(logs: ActivityLog[]) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const buckets = Array.from({ length: 30 }, (_, i) => {
    const d = new Date(today)
    d.setDate(d.getDate() - (29 - i))
    return { date: d.toISOString().split('T')[0], study: 0, habit: 0, milestone: 0 }
  })

  const idx = new Map(buckets.map((b, i) => [b.date, i]))
  for (const log of logs) {
    const i = idx.get(log.event_date)
    if (i !== undefined && (log.event_type === 'study' || log.event_type === 'habit' || log.event_type === 'milestone')) {
      buckets[i][log.event_type]++
    }
  }
  return buckets
}

async function getDashboardData() {
  const thirtyDaysAgo = new Date()
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 29)
  const since = thirtyDaysAgo.toISOString().split('T')[0]

  const [goalsRes, topicsRes, attemptsRes, settingsRes, activityRes, skipsRes] = await Promise.all([
    supabase.from('goals').select('*').order('created_at', { ascending: true }),
    supabase.from('topics').select('*').order('order_index', { ascending: true }),
    supabase
      .from('quiz_attempts')
      .select('*, topics(title)')
      .order('attempted_at', { ascending: false })
      .limit(5),
    supabase.from('settings').select('*').eq('id', 1).single(),
    supabase
      .from('activity_log')
      .select('event_type, event_date')
      .gte('event_date', since)
      .order('event_date', { ascending: true }),
    supabase
      .from('task_skips')
      .select('skipped_at')
      .gte('skipped_at', since + 'T00:00:00+00:00')
      .order('skipped_at', { ascending: true }),
  ])

  const skipRows = (skipsRes.data ?? []) as TaskSkip[]
  return {
    goals: (goalsRes.data ?? []) as Goal[],
    topics: (topicsRes.data ?? []) as Topic[],
    attempts: (attemptsRes.data ?? []) as (QuizAttempt & { topics: { title: string } })[],
    settings: settingsRes.data as Settings | null,
    activityBuckets: buildActivityBuckets((activityRes.data ?? []) as ActivityLog[]),
    skipBuckets: buildSkipBuckets(skipRows),
    totalSkips: skipRows.length,
  }
}

function DeadlineChip({ days }: { days: number | null }) {
  if (days === null) return <span className="text-zinc-500 text-xs">No deadline</span>
  if (days < 0)
    return <span className="text-red-400 text-xs font-medium">{Math.abs(days)}d overdue</span>
  if (days === 0)
    return <span className="text-orange-400 text-xs font-medium">Due today</span>
  return <span className="text-zinc-400 text-xs">{days}d left</span>
}

function OnTrackBadge({ days, total, done }: { days: number | null; total: number; done: number }) {
  if (days === null || total === 0) return null
  const pctDone = done / total
  // rough heuristic: if done% >= expected% by deadline, on track
  const onTrack = days > 0 && pctDone >= 0.3
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
        days < 0
          ? 'bg-red-900 text-red-300'
          : onTrack
          ? 'bg-green-900 text-green-300'
          : 'bg-yellow-900 text-yellow-300'
      }`}
    >
      {days < 0 ? 'Behind' : onTrack ? 'On track' : 'At risk'}
    </span>
  )
}

export default async function DashboardPage() {
  const { goals, topics, attempts, settings, activityBuckets, skipBuckets, totalSkips } = await getDashboardData()

  const streak = settings?.streak ?? 0
  const activeGoals = goals.filter(g => g.status === 'in_progress')

  // Today's suggested topic: first not_started topic under the most urgent active goal
  const topicsForGoal = (goalId: string) => topics.filter(t => t.goal_id === goalId)
  const urgentGoal = [...activeGoals].sort((a, b) => {
    const da = daysUntil(a.target_date) ?? 9999
    const db = daysUntil(b.target_date) ?? 9999
    return da - db
  })[0]

  const suggestedTopic = urgentGoal
    ? topicsForGoal(urgentGoal.id).find(t => t.status === 'not_started')
    : null

  return (
    <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-zinc-100">Dashboard</h1>
        <div className="flex items-center gap-2 bg-zinc-800 px-4 py-2 rounded-xl border border-zinc-700">
          <span className="text-2xl">🔥</span>
          <div>
            <p className="text-xl font-bold text-zinc-100 leading-none">{streak}</p>
            <p className="text-xs text-zinc-500 mt-0.5">day streak</p>
          </div>
        </div>
      </div>

      {/* Suggested topic */}
      {suggestedTopic && urgentGoal && (
        <div className="bg-indigo-950 border border-indigo-700 rounded-xl p-5">
          <p className="text-xs text-indigo-400 font-medium uppercase tracking-wider mb-1">
            Today&apos;s suggested topic
          </p>
          <p className="text-lg font-semibold text-zinc-100">{suggestedTopic.title}</p>
          <p className="text-sm text-zinc-400 mt-1">
            From goal:{' '}
            <Link href={`/goals/${urgentGoal.id}`} className="text-indigo-300 hover:underline">
              {urgentGoal.name}
            </Link>
          </p>
        </div>
      )}

      {/* Active goals */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
            Active Goals
          </h2>
          <Link href="/goals" className="text-xs text-indigo-400 hover:text-indigo-300">
            View all →
          </Link>
        </div>
        {activeGoals.length === 0 ? (
          <div className="bg-zinc-800/50 border border-zinc-700 rounded-xl p-6 text-center">
            <p className="text-zinc-500 text-sm">No active goals yet.</p>
            <Link
              href="/goals"
              className="mt-3 inline-block text-sm text-indigo-400 hover:text-indigo-300"
            >
              Create your first goal →
            </Link>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {activeGoals.map(goal => {
              const goalTopics = topicsForGoal(goal.id)
              const total = goalTopics.length
              const done = countCompleted(goalTopics)
              const pct = total > 0 ? Math.round((done / total) * 100) : 0
              const days = daysUntil(goal.target_date)

              return (
                <Link
                  key={goal.id}
                  href={`/goals/${goal.id}`}
                  className="bg-zinc-800/60 border border-zinc-700 rounded-xl p-5 hover:border-zinc-500 transition-colors block"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="font-medium text-zinc-100">{goal.name}</p>
                    <OnTrackBadge days={days} total={total} done={done} />
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <DeadlineChip days={days} />
                    {goal.target_date && (
                      <span className="text-zinc-600 text-xs">· {formatDate(goal.target_date)}</span>
                    )}
                  </div>
                  {/* Progress bar */}
                  <div className="mt-4">
                    <div className="flex justify-between text-xs text-zinc-500 mb-1">
                      <span>{done}/{total} topics</span>
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
            })}
          </div>
        )}
      </section>

      {/* Recent activity */}
      <section>
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-4">
          Recent Quiz Attempts
        </h2>
        {attempts.length === 0 ? (
          <p className="text-zinc-500 text-sm">No quiz attempts yet.</p>
        ) : (
          <div className="bg-zinc-800/60 border border-zinc-700 rounded-xl divide-y divide-zinc-700/60">
            {attempts.map(a => (
              <div key={a.id} className="flex items-center justify-between px-5 py-3">
                <div>
                  <p className="text-sm text-zinc-100">{a.topics?.title ?? 'Unknown topic'}</p>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    {new Date(a.attempted_at).toLocaleDateString('en-IN', {
                      day: 'numeric',
                      month: 'short',
                      year: 'numeric',
                    })}
                  </p>
                </div>
                <div
                  className={`text-sm font-semibold px-3 py-1 rounded-lg ${
                    a.score >= 4
                      ? 'bg-green-900 text-green-300'
                      : a.score >= 3
                      ? 'bg-yellow-900 text-yellow-300'
                      : 'bg-red-900 text-red-300'
                  }`}
                >
                  {a.score}/5
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Activity graph */}
      <section>
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-4">
          Activity — Last 30 Days
        </h2>
        <div className="bg-zinc-800/60 border border-zinc-700 rounded-xl p-5">
          <ActivityChart days={activityBuckets} />
        </div>
      </section>

      {/* Skip analytics */}
      <section>
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-4">
          Skip Analytics — Last 30 Days
        </h2>
        <div className="bg-zinc-800/60 border border-zinc-700 rounded-xl p-5">
          {totalSkips === 0 ? (
            <p className="text-zinc-500 text-sm">No skips recorded yet — keep it up!</p>
          ) : (
            <SkipChart days={skipBuckets} totalSkips={totalSkips} />
          )}
        </div>
      </section>
    </div>
  )
}
