'use client'

import { useState } from 'react'
import { Settings } from '@/lib/types'
import { supabase } from '@/lib/supabase'
import { formatDate } from '@/lib/utils'

interface Props {
  settings: Settings
}

export default function SettingsClient({ settings }: Props) {
  const [sessionTime, setSessionTime] = useState(settings.daily_session_time)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSaved(false)
    const { error: err } = await supabase
      .from('settings')
      .update({ daily_session_time: sessionTime })
      .eq('id', 1)
    setSaving(false)
    if (err) {
      setError(err.message)
    } else {
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    }
  }

  return (
    <div className="space-y-6">
      {/* Streak card */}
      <div className="bg-zinc-800/60 border border-zinc-700 rounded-xl p-5 flex items-center gap-4">
        <div className="text-4xl">🔥</div>
        <div>
          <p className="text-2xl font-bold text-zinc-100">{settings.streak} days</p>
          <p className="text-sm text-zinc-500">Current streak</p>
          {settings.last_study_date && (
            <p className="text-xs text-zinc-600 mt-0.5">
              Last studied: {formatDate(settings.last_study_date)}
            </p>
          )}
        </div>
      </div>

      {/* Telegram */}
      <div className="bg-zinc-800/60 border border-zinc-700 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-zinc-300 mb-1">Telegram</h2>
        <p className="text-xs text-zinc-500 mb-3">
          Your Telegram user ID — used by the learning bot to send you study reminders.
        </p>
        <div className="flex items-center gap-3">
          <div className="bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2 font-mono text-sm text-zinc-300">
            {settings.telegram_user_id ?? (
              <span className="text-zinc-600">Not configured</span>
            )}
          </div>
          {settings.telegram_user_id && (
            <span className="text-xs text-green-400 bg-green-900/40 px-2 py-0.5 rounded-full">
              Connected
            </span>
          )}
        </div>
        <p className="text-xs text-zinc-600 mt-3">
          To update your Telegram ID, use the /settings command in the bot.
        </p>
      </div>

      {/* Daily session time */}
      <div className="bg-zinc-800/60 border border-zinc-700 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-zinc-300 mb-1">Daily Session Time</h2>
        <p className="text-xs text-zinc-500 mb-4">
          The time each day the bot will prompt you to study.
        </p>
        <form onSubmit={handleSave} className="flex items-center gap-3">
          <input
            type="time"
            value={sessionTime}
            onChange={e => setSessionTime(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500"
          />
          <button
            type="submit"
            disabled={saving}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
          {saved && <span className="text-sm text-green-400">Saved!</span>}
          {error && <span className="text-sm text-red-400">{error}</span>}
        </form>
      </div>
    </div>
  )
}
