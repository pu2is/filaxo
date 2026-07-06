<script setup lang="ts">
import type { ChatResponse, ChoiceItem } from '@/features/chat/types'
import BotMessage from './BotMessage.vue'
import ChoiceGroup from './ChoiceGroup.vue'
import QueryInput from './QueryInput.vue'

defineProps<{ response: ChatResponse }>()
const emit = defineEmits<{
  choice: [choice: ChoiceItem]
  submit: [text: string]
}>()
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="flex-1 space-y-3 overflow-y-auto p-4">
      <BotMessage :message="response.bot_message" />
      <ChoiceGroup :choices="response.choices" @select="emit('choice', $event)" />
    </div>
    <div class="border-t border-border p-4">
      <QueryInput @submit="emit('submit', $event)" />
    </div>
  </div>
</template>
