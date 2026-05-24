'use client'

import { useState } from 'react'
import { Topic } from '@/lib/types'
import { statusIcon, statusColorClass, statusLabel } from '@/lib/utils'
import { supabase } from '@/lib/supabase'
import { useRouter } from 'next/navigation'

interface Props {
  topics: Topic[]
  goalId: string
  onSelectTopic: (topic: Topic) => void
  selectedTopicId: string | null
}

interface NodeProps {
  topic: Topic
  depth: number
  goalId: string
  onSelectTopic: (topic: Topic) => void
  selectedTopicId: string | null
}

function AddSubtopicInline({
  parentId,
  goalId,
  onDone,
}: {
  parentId: string
  goalId: string
  onDone: () => void
}) {
  const [title, setTitle] = useState('')
  const [saving, setSaving] = useState(false)
  const router = useRouter()

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    setSaving(true)
    await supabase.from('topics').insert({
      goal_id: goalId,
      parent_id: parentId,
      title: title.trim(),
      status: 'not_started',
      order_index: 0,
    })
    setSaving(false)
    onDone()
    router.refresh()
  }

  return (
    <form
      onSubmit={handleAdd}
      className="flex items-center gap-2 mt-2"
      onClick={e => e.stopPropagation()}
    >
      <input
        type="text"
        value={title}
        onChange={e => setTitle(e.target.value)}
        placeholder="Sub-topic title…"
        autoFocus
        className="flex-1 bg-zinc-800 border border-zinc-700 rounded-md px-2 py-1 text-xs text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-indigo-500"
      />
      <button
        type="submit"
        disabled={saving}
        className="text-xs bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-3 py-1 rounded-md"
      >
        Add
      </button>
      <button
        type="button"
        onClick={onDone}
        className="text-xs text-zinc-500 hover:text-zinc-300 px-2 py-1"
      >
        Cancel
      </button>
    </form>
  )
}

function TopicNode({ topic, depth, goalId, onSelectTopic, selectedTopicId }: NodeProps) {
  const [expanded, setExpanded] = useState(true)
  const [addingChild, setAddingChild] = useState(false)
  const hasChildren = topic.children && topic.children.length > 0
  const isSelected = topic.id === selectedTopicId

  return (
    <div style={{ paddingLeft: depth > 0 ? '1.25rem' : '0' }}>
      <div
        className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors ${
          isSelected
            ? 'bg-indigo-900/50 border border-indigo-700'
            : 'hover:bg-zinc-800/60 border border-transparent'
        }`}
        onClick={() => onSelectTopic(topic)}
      >
        {/* Expand toggle */}
        <button
          onClick={e => {
            e.stopPropagation()
            setExpanded(v => !v)
          }}
          className={`text-xs text-zinc-600 hover:text-zinc-300 w-4 shrink-0 ${
            !hasChildren ? 'invisible' : ''
          }`}
        >
          {expanded ? '▾' : '▸'}
        </button>

        {/* Status icon */}
        <span className="text-sm shrink-0">{statusIcon(topic.status)}</span>

        {/* Title */}
        <span className="flex-1 text-sm text-zinc-200">{topic.title}</span>

        {/* Score */}
        {topic.score && (
          <span className="text-xs text-zinc-500 shrink-0">{topic.score}</span>
        )}

        {/* Status badge */}
        <span
          className={`text-xs px-2 py-0.5 rounded-full shrink-0 hidden sm:block ${statusColorClass(
            topic.status
          )}`}
        >
          {statusLabel(topic.status)}
        </span>

        {/* Add sub-topic button */}
        <button
          onClick={e => {
            e.stopPropagation()
            setAddingChild(true)
            setExpanded(true)
          }}
          className="text-xs text-zinc-600 hover:text-indigo-400 opacity-0 group-hover:opacity-100 shrink-0 transition-opacity"
          title="Add sub-topic"
        >
          + sub
        </button>
      </div>

      {/* Inline add form */}
      {addingChild && (
        <div className="pl-10">
          <AddSubtopicInline
            parentId={topic.id}
            goalId={goalId}
            onDone={() => setAddingChild(false)}
          />
        </div>
      )}

      {/* Children */}
      {hasChildren && expanded && (
        <div className="border-l border-zinc-800 ml-5 mt-0.5">
          {topic.children!.map(child => (
            <TopicNode
              key={child.id}
              topic={child}
              depth={depth + 1}
              goalId={goalId}
              onSelectTopic={onSelectTopic}
              selectedTopicId={selectedTopicId}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function TopicTree({ topics, goalId, onSelectTopic, selectedTopicId }: Props) {
  const [addingTop, setAddingTop] = useState(false)
  const router = useRouter()

  async function handleAddTop(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget
    const titleInput = form.elements.namedItem('title') as HTMLInputElement
    const title = titleInput.value.trim()
    if (!title) return
    await supabase.from('topics').insert({
      goal_id: goalId,
      parent_id: null,
      title,
      status: 'not_started',
      order_index: topics.length,
    })
    setAddingTop(false)
    router.refresh()
  }

  return (
    <div className="space-y-0.5">
      {topics.length === 0 && !addingTop && (
        <p className="text-sm text-zinc-500 py-4">
          No topics yet. Add your first topic below.
        </p>
      )}

      {topics.map(topic => (
        <TopicNode
          key={topic.id}
          topic={topic}
          depth={0}
          goalId={goalId}
          onSelectTopic={onSelectTopic}
          selectedTopicId={selectedTopicId}
        />
      ))}

      {/* Add top-level topic */}
      <div className="pt-3">
        {addingTop ? (
          <form onSubmit={handleAddTop} className="flex items-center gap-2">
            <input
              name="title"
              type="text"
              placeholder="Topic title…"
              autoFocus
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-md px-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              className="text-sm bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-1.5 rounded-md"
            >
              Add
            </button>
            <button
              type="button"
              onClick={() => setAddingTop(false)}
              className="text-sm text-zinc-500 hover:text-zinc-300 px-2 py-1.5"
            >
              Cancel
            </button>
          </form>
        ) : (
          <button
            onClick={() => setAddingTop(true)}
            className="text-sm text-zinc-500 hover:text-indigo-400 flex items-center gap-1.5 transition-colors"
          >
            <span className="text-lg leading-none">+</span> Add topic
          </button>
        )}
      </div>
    </div>
  )
}
