// Mirrors backend/modules/chat/schemas.py field-for-field (see #18) -- keep names and
// optionality in sync with that file, not camelCase-converted, so there's no translation
// layer to keep in sync on top of the contract itself.

export interface ChoiceItem {
  id: string // sent back as ChatRequest.payload when the choice is clicked
  label: string // button text shown to the user (German)
  action: ChatAction // sent back as ChatRequest.action when the choice is clicked (#22)
}

export interface SuggestionItem {
  id: string
  label: string
}

export type ChatAction =
  | 'start'
  | 'select_domain'
  | 'confirm_domain'
  | 'select_time'
  | 'proceed'
  | 'query'

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
