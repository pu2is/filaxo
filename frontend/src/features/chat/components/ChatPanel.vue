<script setup lang="ts">
import { onMounted } from 'vue'

import { useChat } from '@/features/chat/composables/useChat'
import type { ChoiceItem } from '@/features/chat/types'
import BotMessage from './BotMessage.vue'
import ChoiceGroup from './ChoiceGroup.vue'
import QueryInput from './QueryInput.vue'

const { current, isLoading, sendAction } = useChat()

onMounted(() => {
  sendAction('start')
})

function handleChoice(choice: ChoiceItem) {
  sendAction('select_domain', choice.id)
}

function handleSubmit(text: string) {
  // Free-text/query wiring lands in a later goal -- see #20's scope cut.
  console.log('query submitted:', text)
}
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="flex-1 space-y-3 overflow-y-auto p-4">
      <BotMessage v-if="current" :message="current.bot_message" />
      <ChoiceGroup
        v-if="current"
        :choices="current.choices"
        :disabled="isLoading"
        @select="handleChoice"
      />
    </div>
    <div class="border-t border-border p-4">
      <QueryInput @submit="handleSubmit" />
    </div>
  </div>
</template>
