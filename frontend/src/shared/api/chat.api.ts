import type { ChatRequest, ChatResponse } from '@/features/chat/types'
import { apiPost } from '@/shared/api/client'

export function sendChat(request: ChatRequest): Promise<ChatResponse> {
  return apiPost<ChatResponse>('/api/chat', request)
}
