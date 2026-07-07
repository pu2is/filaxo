<script setup lang="ts">
import { onMounted } from 'vue'

import { useChatStore } from '@/features/chat/stores/chat.store'
import type { BreadcrumbItem, ChoiceItem } from '@/features/chat/types'
import ChoiceGroup from './ChoiceGroup.vue'
import DateRangePicker from './DateRangePicker.vue'
import MessageHistory from './MessageHistory.vue'
import QueryInput from './QueryInput.vue'
import ScopeBreadcrumb from './ScopeBreadcrumb.vue'

const chat = useChatStore()

onMounted(() => {
  // Guard against a remount double-greeting -- the store outlives this component.
  if (chat.history.length === 0) {
    chat.sendAction('start')
  }
})

function handleChoice(choice: ChoiceItem) {
  // Server-driven routing: each choice carries the action the backend expects back (#22).
  // Tree-drill choices (select_scope) need no special handling here -- the backend
  // already put the right action/id/label on the choice (#31).
  chat.sendAction(choice.action, choice.id, choice.label)
}

function handleTruncate(crumb: BreadcrumbItem) {
  // #32: clicking a breadcrumb chip's × truncates back to before that level.
  chat.sendAction('truncate_scope', crumb.key, `Zurück: ${crumb.label}`)
}

function handleSubmit(text: string) {
  // Big Goal 4 marker (#26): the typed question goes to the backend as a real
  // "query" action -- payload and the echoed user-reply text are the same string.
  chat.sendAction('query', text, text)
}

function handleTimeRangeSubmit(dateFrom: string, dateTo: string) {
  chat.setTimeRange(dateFrom, dateTo)
}
</script>

<template>
  <div class="flex h-full flex-col">
    <header class="flex shrink-0 items-center justify-between border-b border-border px-4 py-3">
      <h1 class="text-sm font-semibold">Filax.One CRM-Assistent</h1>
      <button
        type="button"
        :disabled="chat.isLoading"
        class="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
        @click="chat.restart()"
      >
        Neu starten
      </button>
    </header>
    <MessageHistory :history="chat.history" :is-loading="chat.isLoading" />
    <div v-if="chat.activeBreadcrumb.length" class="shrink-0 border-t border-border px-4 py-2">
      <ScopeBreadcrumb :crumbs="chat.activeBreadcrumb" :disabled="chat.isLoading" @remove="handleTruncate" />
    </div>
    <div v-if="chat.activeAwaitingTimeRange" class="shrink-0 border-t border-border p-4">
      <!-- D6/#37: date-range picker takes over the whole input area for this turn --
           there's nothing to choose or type freely at the time step. -->
      <DateRangePicker :disabled="chat.isLoading" @submit="handleTimeRangeSubmit" />
    </div>
    <template v-else>
      <div v-if="chat.activeChoices.length" class="shrink-0 border-t border-border p-4">
        <ChoiceGroup :choices="chat.activeChoices" :disabled="chat.isLoading" @select="handleChoice" />
      </div>
      <div class="shrink-0 border-t border-border p-4">
        <QueryInput :disabled="chat.isLoading" @submit="handleSubmit" />
      </div>
    </template>
  </div>
</template>
