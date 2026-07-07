// Mirrors backend/modules/chat/schemas.py field-for-field (see #18, updated in #26 for
// ResultPayload/#25) -- keep names and optionality in sync with that file, not
// camelCase-converted, so there's no translation layer to keep in sync on top of the
// contract itself.

export interface ChoiceItem {
  id: string // sent back as ChatRequest.payload when the choice is clicked
  label: string // button text shown to the user (German)
  action: ChatAction // sent back as ChatRequest.action when the choice is clicked (#22)
}

export interface SuggestionItem {
  id: string
  label: string
}

// 'proceed' (the BG3 scope add-on's skip action) was removed backend-side in #25 --
// D5 moved cross-thema selection to MVP 2, so there's no add-on step to skip anymore.
export type ChatAction = 'start' | 'select_domain' | 'confirm_domain' | 'select_time' | 'query'

export interface ChatRequest {
  session_id?: string | null
  action: ChatAction
  payload?: string | null
}

export interface SourceItem {
  table: string
  doc_ref: string
}

export interface ResultColumn {
  name: string
  type: string | null
}

export interface ResultPayload {
  rows: Record<string, unknown>[]
  columns: ResultColumn[]
  chart_type: 'table'
  sql: string | null
  sources: SourceItem[]
}

export interface ChatResponse {
  session_id: string
  bot_message: string
  choices: ChoiceItem[]
  suggestions: SuggestionItem[]
  show_input: boolean
  result: ResultPayload | null
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
