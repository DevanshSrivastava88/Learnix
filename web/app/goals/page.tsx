import { supabase } from '@/lib/supabase'
import { Goal, Topic } from '@/lib/types'
import { countCompleted } from '@/lib/utils'
import GoalCard from '@/components/GoalCard'
import NewGoalButton from '@/components/NewGoalButton'

export const revalidate = 60

async function getGoals(): Promise<Goal[]> {
  const [goalsRes, topicsRes] = await Promise.all([
    supabase.from('goals').select('*').order('created_at', { ascending: true }),
    supabase.from('topics').select('id, goal_id, status'),
  ])

  const goals = (goalsRes.data ?? []) as Goal[]
  const topics = (topicsRes.data ?? []) as Pick<Topic, 'id' | 'goal_id' | 'status'>[]

  return goals.map(g => {
    const gt = topics.filter(t => t.goal_id === g.id)
    return {
      ...g,
      topic_count: gt.length,
      completed_topic_count: gt.filter(t => t.status === 'passed').length,
    }
  })
}

export default async function GoalsPage() {
  const goals = await getGoals()
  const active = goals.filter(g => g.status === 'in_progress')
  const others = goals.filter(g => g.status !== 'in_progress')

  return (
    <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">Goals</h1>
          <p className="text-sm text-zinc-500 mt-1">
            {goals.length} goal{goals.length !== 1 ? 's' : ''} total
          </p>
        </div>
        <NewGoalButton />
      </div>

      {/* Active goals */}
      {active.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
            Active
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {active.map(g => (
              <GoalCard key={g.id} goal={g} />
            ))}
          </div>
        </section>
      )}

      {/* Other goals */}
      {others.length > 0 && (
        <section>
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
            Other
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {others.map(g => (
              <GoalCard key={g.id} goal={g} />
            ))}
          </div>
        </section>
      )}

      {goals.length === 0 && (
        <div className="bg-zinc-800/50 border border-zinc-700 rounded-xl p-12 text-center">
          <p className="text-zinc-400 font-medium">No goals yet</p>
          <p className="text-sm text-zinc-600 mt-1">
            Create your first goal to start tracking your learning journey.
          </p>
        </div>
      )}
    </div>
  )
}
