<script setup lang="ts">
import { onMounted } from 'vue'

import { useChatStore } from '@/features/chat/stores/chat.store'
import type { ChoiceItem } from '@/features/chat/types'
import ChoiceGroup from './ChoiceGroup.vue'
import MessageHistory from './MessageHistory.vue'
import QueryInput from './QueryInput.vue'

const chat = useChatStore()

onMounted(() => {
  // Guard against a remount double-greeting -- the store outlives this component.
  if (chat.history.length === 0) {
    chat.sendAction('start')
  }
})

function handleChoice(choice: ChoiceItem) {
  // Still hardcoded to select_domain -- choice-to-action routing is Big Goal 3 scope (#21).
  chat.sendAction('select_domain', choice.id, choice.label)
}

function handleSubmit(text: string) {
  // Free-text/query wiring lands in a later goal -- see #20's scope cut.
  console.log('query submitted:', text)
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
    <MessageHistory :history="chat.history" />
    <div v-if="chat.activeChoices.length" class="shrink-0 border-t border-border p-4">
      <ChoiceGroup :choices="chat.activeChoices" :disabled="chat.isLoading" @select="handleChoice" />
    </div>
    <div class="shrink-0 border-t border-border p-4">
      <QueryInput @submit="handleSubmit" />
    </div>
  </div>
</template>
