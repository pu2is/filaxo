<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{ submit: [text: string] }>()
const text = ref('')

function handleSubmit() {
  const trimmed = text.value.trim()
  if (!trimmed) return
  emit('submit', trimmed)
  text.value = ''
}
</script>

<template>
  <form class="flex gap-2" @submit.prevent="handleSubmit">
    <input
      v-model="text"
      type="text"
      placeholder="Ihre Frage eingeben..."
      class="flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
    />
    <button
      type="submit"
      class="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:opacity-90"
    >
      Senden
    </button>
  </form>
</template>
