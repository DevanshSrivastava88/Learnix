import { supabase } from '@/lib/supabase'
import { Settings } from '@/lib/types'
import SettingsClient from './SettingsClient'

export const revalidate = 60

async function getSettings(): Promise<Settings | null> {
  const { data } = await supabase.from('settings').select('*').eq('id', 1).single()
  return data as Settings | null
}

export default async function SettingsPage() {
  const settings = await getSettings()

  return (
    <div className="p-6 md:p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-semibold text-zinc-100 mb-1">Settings</h1>
      <p className="text-sm text-zinc-500 mb-8">Manage your study preferences.</p>

      {settings ? (
        <SettingsClient settings={settings} />
      ) : (
        <div className="bg-red-900/30 border border-red-700 rounded-xl p-5 text-sm text-red-300">
          Could not load settings. Make sure the settings table has a row with id=1.
        </div>
      )}
    </div>
  )
}
