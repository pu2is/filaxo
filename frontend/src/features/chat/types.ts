// Mirrors backend/modules/chat/schemas.py field-for-field (see #18) -- keep names and
// optionality in sync with that file, not camelCase-converted, so there's no translation
// layer to keep in sync on top of the contract itself.

export interface ChoiceItem {
  id: string
  label: string
}

export interface SuggestionItem {
  id: string
  label: string
}

export type ChatAction = 'start' | 'select_domain' | 'confirm_domain' | 'select_time' | 'query'

export interface ChatRequest {
  session_id?: string | null
  action: ChatAction
  payload?: string | null
}

export interface ChatResponse {
  session_id: string
  bot_message: string
  choices: ChoiceItem[]
  suggestions: SuggestionItem[]
  show_input: boolean
  result: Record<string, unknown> | null
}

// --- Frontend-only view types below: NOT part of the backend contract. ---

export interface UserReplyEntry {
  kind: 'user'
  id: string
  text: string
}

export interface BotTurnEntry {
  kind: 'bot'
  id: string
  response: ChatResponse
}

export type HistoryEntry = UserReplyEntry | BotTurnEntry
