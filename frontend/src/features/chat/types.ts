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
// #31 (D5 tree drilling): "select_scope" payload is the FULL dotted node path (e.g.
// "LEAD.SCORING", matching a ChoiceItem.id from the scope step); "truncate_scope" payload
// is just the single segment key to cut back to (e.g. "SCORING"), matching a
// scope_breadcrumb entry's `key`.
export type ChatAction =
  | 'start'
  | 'select_domain'
  | 'select_scope'
  | 'truncate_scope'
  | 'confirm_domain'
  | 'set_time_range'
  | 'continue_topic'
  | 'change_topic'
  | 'change_time_range'
  | 'keep_time_range'
  | 'query'

export interface ChatRequest {
  session_id?: string | null
  action: ChatAction
  payload?: string | null
  // set_time_range only (D6, #34/#37): ISO YYYY-MM-DD, as typed/picked by the user.
  date_from?: string | null
  date_to?: string | null
}

export interface BreadcrumbItem {
  key: string // single path segment -- this is truncate_scope's payload when its × is clicked
  label: string // German label for that segment
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
  scope_breadcrumb: BreadcrumbItem[] // server-truth scope-tree path walked so far (#31)
  // True only at the time step (D6, #34): render a date-range picker instead of choices.
  awaiting_time_range: boolean
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
