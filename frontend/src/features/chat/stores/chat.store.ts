import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { ChatAction, ChatRequest, HistoryEntry } from '@/features/chat/types'
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

  // D6/#37: true only right after the time step's prompt -- ChatPanel swaps in the date
  // picker instead of ChoiceGroup/QueryInput for that turn.
  const activeAwaitingTimeRange = computed(() => {
    const last = history.value[history.value.length - 1]
    return last?.kind === 'bot' ? last.response.awaiting_time_range : false
  })

  // Shared by sendAction/setTimeRange below: send the request, land the bot turn, and
  // manage isLoading -- the two callers only differ in what they push as the user's own
  // reply bubble before calling this.
  async function _dispatch(request: ChatRequest) {
    isLoading.value = true
    try {
      const response = await sendChat(request)
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

  async function sendAction(action: ChatAction, payload?: string, userReplyText?: string) {
    if (isLoading.value) return
    if (userReplyText) {
      history.value.push({ kind: 'user', id: crypto.randomUUID(), text: userReplyText })
    }
    await _dispatch({ session_id: sessionId.value, action, payload })
  }

  // D6/#37: set_time_range needs two values (date_from/date_to), which ChatRequest carries
  // as dedicated fields rather than the single payload string sendAction sends -- bypasses
  // sendAction rather than bolting a second optional param onto its signature.
  async function setTimeRange(dateFrom: string, dateTo: string) {
    if (isLoading.value) return
    history.value.push({ kind: 'user', id: crypto.randomUUID(), text: `Zeitraum: ${dateFrom} bis ${dateTo}` })
    await _dispatch({ session_id: sessionId.value, action: 'set_time_range', date_from: dateFrom, date_to: dateTo })
  }

  function restart() {
    if (isLoading.value) return
    sessionId.value = null
    history.value = []
    // session_id: null mints a fresh session server-side -- no backend change needed.
    void sendAction('start')
  }

  return {
    sessionId,
    history,
    isLoading,
    activeChoices,
    activeBreadcrumb,
    activeAwaitingTimeRange,
    sendAction,
    setTimeRange,
    restart,
  }
})
