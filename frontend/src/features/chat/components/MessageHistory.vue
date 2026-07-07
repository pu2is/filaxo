<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

import type { HistoryEntry } from '@/features/chat/types'
import DataTable from '@/features/result/components/DataTable.vue'
import BotMessage from './BotMessage.vue'
import ThinkingIndicator from './ThinkingIndicator.vue'
import UserReply from './UserReply.vue'

const props = defineProps<{ history: HistoryEntry[]; isLoading: boolean }>()

const container = ref<HTMLElement | null>(null)

watch(
  [() => props.history.length, () => props.isLoading],
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
      <template v-else>
        <BotMessage :message="entry.response.bot_message" />
        <DataTable v-if="entry.response.result" :result="entry.response.result" />
      </template>
    </template>
    <ThinkingIndicator v-if="isLoading" />
  </div>
</template>
