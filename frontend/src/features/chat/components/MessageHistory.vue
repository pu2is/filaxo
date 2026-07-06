<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

import type { HistoryEntry } from '@/features/chat/types'
import BotMessage from './BotMessage.vue'
import UserReply from './UserReply.vue'

const props = defineProps<{ history: HistoryEntry[] }>()

const container = ref<HTMLElement | null>(null)

watch(
  () => props.history.length,
  async () => {
    await nextTick()
    container.value?.scrollTo({ top: container.value.scrollHeight })
  },
)
</script>

<template>
  <div ref="container" class="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
    <template v-for="entry in history" :key="entry.id">
      <UserReply v-if="entry.kind === 'user'" :text="entry.text" />
      <BotMessage v-else :message="entry.response.bot_message" />
    </template>
  </div>
</template>
