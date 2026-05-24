import { Topic, TopicStatus } from './types'

/** Build a nested tree from a flat list of topics. */
export function buildTopicTree(flat: Topic[]): Topic[] {
  const map = new Map<string, Topic>()
  flat.forEach(t => map.set(t.id, { ...t, children: [] }))

  const roots: Topic[] = []
  map.forEach(t => {
    if (t.parent_id && map.has(t.parent_id)) {
      map.get(t.parent_id)!.children!.push(t)
    } else {
      roots.push(t)
    }
  })

  // sort by order_index at every level
  const sort = (nodes: Topic[]) => {
    nodes.sort((a, b) => a.order_index - b.order_index)
    nodes.forEach(n => n.children && sort(n.children))
  }
  sort(roots)
  return roots
}

/** Days remaining until a date string (positive = future, negative = past). */
export function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null
  const target = new Date(dateStr)
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  target.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - now.getTime()) / 86_400_000)
}

export function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function statusLabel(status: TopicStatus): string {
  return {
    not_started: 'Not started',
    in_progress: 'In progress',
    passed: 'Passed',
    needs_revision: 'Needs revision',
  }[status]
}

export function statusIcon(status: TopicStatus): string {
  return {
    not_started: '🔲',
    in_progress: '⏳',
    passed: '✅',
    needs_revision: '⚠️',
  }[status]
}

export function statusColorClass(status: TopicStatus): string {
  return {
    not_started: 'text-zinc-500 bg-zinc-800',
    in_progress: 'text-yellow-400 bg-yellow-950',
    passed: 'text-green-400 bg-green-950',
    needs_revision: 'text-orange-400 bg-orange-950',
  }[status]
}

/** Count all topics in a flat list that are passed. */
export function countCompleted(topics: Topic[]): number {
  return topics.filter(t => t.status === 'passed').length
}
