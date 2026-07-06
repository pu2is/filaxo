<script setup lang="ts">
import type { ChoiceItem } from '@/features/chat/types'

defineProps<{ choices: ChoiceItem[]; disabled?: boolean }>()
const emit = defineEmits<{ select: [choice: ChoiceItem] }>()
</script>

<template>
  <div v-if="choices.length" class="flex flex-wrap gap-2">
    <button
      v-for="choice in choices"
      :key="choice.id"
      type="button"
      :disabled="disabled"
      class="rounded-full border border-border bg-background px-4 py-1.5 text-sm hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
      @click="emit('select', choice)"
    >
      {{ choice.label }}
    </button>
  </div>
</template>
