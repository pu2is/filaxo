import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { ChatAction, HistoryEntry } from '@/features/chat/types'
import { sendChat } from '@/shared/api/chat.api'

export const useChatStore = defineStore('chat', () => {
  const sessionId = ref<string | null>(null)
  const history = ref<HistoryEntry[]>([])
  const isLoading = ref(false)

  // Only the newest bot turn offers choices -- historical turns render as plain bubbles.
  const activeChoices = computed(() => {
    const last = history.value[history.value.length - 1]
    return last?.kind === 'bot' ? last.response.choices : []
  })

  // Same idea for the scope breadcrumb (#31/#32) -- server-truth path as of the latest turn.
  const activeBreadcrumb = computed(() => {
    const last = history.value[history.value.length - 1]
    return last?.kind === 'bot' ? last.response.scope_breadcrumb : []
  })

  async function sendAction(action: ChatAction, payload?: string, userReplyText?: string) {
    if (isLoading.value) return
    isLoading.value = true
    if (userReplyText) {
      history.value.push({ kind: 'user', id: crypto.randomUUID(), text: userReplyText })
    }
    try {
      const response = await sendChat({ session_id: sessionId.value, action, payload })
      sessionId.value = response.session_id
      history.value.push({ kind: 'bot', id: crypto.randomUUID(), response })
    } catch (error) {
      // No dedicated error UI yet (later goal) -- just don't let a failed
      // request take the app down or leave isLoading stuck true.
      console.error('sendChat failed:', error)
    } finally {
      isLoading.value = false
    }
  }

  function restart() {
    if (isLoading.value) return
    sessionId.value = null
    history.value = []
    // session_id: null mints a fresh session server-side -- no backend change needed.
    void sendAction('start')
  }

  return { sessionId, history, isLoading, activeChoices, activeBreadcrumb, sendAction, restart }
})
