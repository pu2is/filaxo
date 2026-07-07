<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{ submit: [dateFrom: string, dateTo: string] }>()

const dateFrom = ref('')
const dateTo = ref('')

function handleSubmit() {
  if (props.disabled) return
  if (!dateFrom.value || !dateTo.value) return
  // Convenience only (#37): native date inputs give YYYY-MM-DD, so string comparison is
  // chronological order too -- the backend re-validates independently (#34) either way.
  if (dateFrom.value > dateTo.value) return
  emit('submit', dateFrom.value, dateTo.value)
}
</script>

<template>
  <form class="flex flex-wrap items-center gap-2" @submit.prevent="handleSubmit">
    <input
      v-model="dateFrom"
      type="date"
      :disabled="disabled"
      class="rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
    />
    <span class="text-sm text-muted-foreground">bis</span>
    <input
      v-model="dateTo"
      type="date"
      :disabled="disabled"
      class="rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
    />
    <button
      type="submit"
      :disabled="disabled"
      class="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
    >
      Anwenden
    </button>
  </form>
</template>
