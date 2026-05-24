export type GoalStatus = 'in_progress' | 'completed' | 'abandoned'

export interface Goal {
  id: string
  name: string
  description: string | null
  target_date: string | null
  status: GoalStatus
  created_at: string
  // computed — populated by data-fetching helpers
  topic_count?: number
  completed_topic_count?: number
}

export type TopicStatus = 'not_started' | 'in_progress' | 'passed' | 'needs_revision'

export interface Topic {
  id: string
  goal_id: string
  parent_id: string | null
  title: string
  description: string | null
  notes: string | null
  status: TopicStatus
  score: string | null
  order_index: number
  completed_at: string | null
  created_at: string
  // tree helpers — populated client-side
  children?: Topic[]
}

export interface QuizAttempt {
  id: string
  topic_id: string
  score: number
  attempted_at: string
}

export interface Settings {
  id: number
  daily_session_time: string
  telegram_user_id: number | null
  streak: number
  last_study_date: string | null
}
