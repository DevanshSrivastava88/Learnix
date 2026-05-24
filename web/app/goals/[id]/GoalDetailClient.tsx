'use client'

import { useState } from 'react'
import { Topic } from '@/lib/types'
import TopicTree from '@/components/TopicTree'
import TopicPanel from '@/components/TopicPanel'

interface Props {
  goalId: string
  topicTree: Topic[]
  allTopics: Topic[]
}

export default function GoalDetailClient({ goalId, topicTree, allTopics }: Props) {
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null)
  const selectedTopic = selectedTopicId
    ? allTopics.find(t => t.id === selectedTopicId) ?? null
    : null

  function handleSelectTopic(topic: Topic) {
    setSelectedTopicId(prev => (prev === topic.id ? null : topic.id))
  }

  return (
    <div>
      <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">
        Topics
      </h2>
      <TopicTree
        topics={topicTree}
        goalId={goalId}
        onSelectTopic={handleSelectTopic}
        selectedTopicId={selectedTopicId}
      />

      <TopicPanel
        topic={selectedTopic}
        onClose={() => setSelectedTopicId(null)}
      />
    </div>
  )
}
