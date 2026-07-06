import { ref } from 'vue'

import type { ChatAction, ChatResponse } from '@/features/chat/types'
import { sendChat } from '@/shared/api/chat.api'

export function useChat() {
  const sessionId = ref<string | null>(null)
  const current = ref<ChatResponse | null>(null)
  const isLoading = ref(false)

  async function sendAction(action: ChatAction, payload?: string) {
    if (isLoading.value) return
    isLoading.value = true
    try {
      const response = await sendChat({ session_id: sessionId.value, action, payload })
      sessionId.value = response.session_id
      current.value = response
    } catch (error) {
      // No dedicated error UI yet (later goal) -- just don't let a failed
      // request take the app down or leave isLoading stuck true.
      console.error('sendChat failed:', error)
    } finally {
      isLoading.value = false
    }
  }

  return { sessionId, current, isLoading, sendAction }
}
