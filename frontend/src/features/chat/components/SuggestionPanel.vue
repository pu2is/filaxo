<script setup lang="ts">
import { ref } from 'vue'

import type { SuggestionItem } from '@/features/chat/types'

defineProps<{ suggestions: SuggestionItem[]; disabled?: boolean }>()
const emit = defineEmits<{ select: [suggestion: SuggestionItem] }>()

// D8/#38: collapsed by default -- the panel is a fallback for "I don't know what to ask",
// not the primary input, so it shouldn't compete with the query box for attention.
const expanded = ref(false)
</script>

<template>
  <div>
    <button
      type="button"
      :aria-expanded="expanded"
      class="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      @click="expanded = !expanded"
    >
      <span class="inline-block transition-transform" :class="{ 'rotate-90': expanded }">▸</span>
      Fragen-Vorschläge ({{ suggestions.length }})
    </button>
    <!-- grid-template-rows 0fr<->1fr: animates to the content's natural height without
         measuring it in JS, and handles a variable number/length of suggestions for free. -->
    <div class="suggestion-collapse" :class="{ 'suggestion-collapse--open': expanded }">
      <div class="overflow-hidden">
        <div class="flex flex-wrap gap-2 pt-2">
          <button
            v-for="s in suggestions"
            :key="s.id"
            type="button"
            :disabled="disabled"
            class="rounded-full border border-border bg-background px-4 py-1.5 text-sm hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
            @click="emit('select', s)"
          >
            {{ s.label }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.suggestion-collapse {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.25s ease;
}

.suggestion-collapse--open {
  grid-template-rows: 1fr;
}

@media (prefers-reduced-motion: reduce) {
  .suggestion-collapse {
    transition: none;
  }
}
</style>
