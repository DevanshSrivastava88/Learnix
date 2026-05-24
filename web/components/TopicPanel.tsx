'use client'

import { useEffect, useState, useCallback } from 'react'
import { Topic, QuizAttempt, TopicStatus } from '@/lib/types'
import { statusColorClass, statusLabel, statusIcon, formatDate } from '@/lib/utils'
import { supabase } from '@/lib/supabase'
import { useRouter } from 'next/navigation'

interface Props {
  topic: Topic | null
  onClose: () => void
}

const STATUS_OPTIONS: TopicStatus[] = ['not_started', 'in_progress', 'passed', 'needs_revision']

export default function TopicPanel({ topic, onClose }: Props) {
  const [title, setTitle] = useState('')
  const [notes, setNotes] = useState('')
  const [status, setStatus] = useState<TopicStatus>('not_started')
  const [attempts, setAttempts] = useState<QuizAttempt[]>([])
  const [savingNotes, setSavingNotes] = useState(false)
  const [savingTitle, setSavingTitle] = useState(false)
  const router = useRouter()

  useEffect(() => {
    if (!topic) return
    setTitle(topic.title)
    setNotes(topic.notes ?? '')
    setStatus(topic.status)

    supabase
      .from('quiz_attempts')
      .select('*')
      .eq('topic_id', topic.id)
      .order('attempted_at', { ascending: false })
      .then(({ data }) => setAttempts((data ?? []) as QuizAttempt[]))
  }, [topic])

  const saveNotes = useCallback(async () => {
    if (!topic) return
    setSavingNotes(true)
    await supabase.from('topics').update({ notes }).eq('id', topic.id)
    setSavingNotes(false)
  }, [topic, notes])

  async function saveTitle() {
    if (!topic || !title.trim()) return
    setSavingTitle(true)
    await supabase.from('topics').update({ title: title.trim() }).eq('id', topic.id)
    setSavingTitle(false)
    router.refresh()
  }

  async function handleStatusChange(newStatus: TopicStatus) {
    if (!topic) return
    setStatus(newStatus)
    const update: Record<string, unknown> = { status: newStatus }
    if (newStatus === 'passed') update.completed_at = new Date().toISOString()
    else update.completed_at = null
    await supabase.from('topics').update(update).eq('id', topic.id)
    router.refresh()
  }

  if (!topic) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-30 bg-black/40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-full max-w-md z-40 bg-zinc-900 border-l border-zinc-800 flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
          <span className="text-sm text-zinc-500">Topic detail</span>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-200 text-xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {/* Title */}
          <div>
            <label className="block text-xs text-zinc-500 mb-1.5">Title</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={title}
                onChange={e => setTitle(e.target.value)}
                onBlur={saveTitle}
                className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500"
              />
              {savingTitle && (
                <span className="text-xs text-zinc-500 self-center">saving…</span>
              )}
            </div>
          </div>

          {/* Status */}
          <div>
            <label className="block text-xs text-zinc-500 mb-2">Status</label>
            <div className="flex flex-wrap gap-2">
              {STATUS_OPTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => handleStatusChange(s)}
                  className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all ${
                    status === s
                      ? statusColorClass(s) + ' ring-2 ring-offset-1 ring-offset-zinc-900 ring-indigo-500'
                      : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
                  }`}
                >
                  {statusIcon(s)} {statusLabel(s)}
                </button>
              ))}
            </div>
          </div>

          {/* Notes */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs text-zinc-500">Notes</label>
              {savingNotes && <span className="text-xs text-zinc-600">saving…</span>}
            </div>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              onBlur={saveNotes}
              placeholder="Add notes about this topic…"
              rows={10}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-indigo-500 resize-y"
            />
          </div>

          {/* Quiz history */}
          <div>
            <h3 className="text-xs text-zinc-500 mb-3">Quiz History</h3>
            {attempts.length === 0 ? (
              <p className="text-xs text-zinc-600">No quiz attempts yet.</p>
            ) : (
              <div className="space-y-2">
                {attempts.map(a => (
                  <div
                    key={a.id}
                    className="flex items-center justify-between bg-zinc-800 rounded-lg px-3 py-2"
                  >
                    <span className="text-xs text-zinc-400">
                      {formatDate(a.attempted_at)}
                    </span>
                    <span
                      className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                        a.score >= 4
                          ? 'bg-green-900 text-green-300'
                          : a.score >= 3
                          ? 'bg-yellow-900 text-yellow-300'
                          : 'bg-red-900 text-red-300'
                      }`}
                    >
                      {a.score}/5
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
