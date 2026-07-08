<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{ submit: [dateFrom: string | null, dateTo: string | null] }>()

const fromYear = ref('')
const fromMonth = ref('')
const fromDay = ref('')
const toYear = ref('')
const toMonth = ref('')
const toDay = ref('')

const YEARS = Array.from({ length: 41 }, (_, i) => String(1990 + i))
const MONTHS = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, '0'))
const DAYS = Array.from({ length: 31 }, (_, i) => String(i + 1).padStart(2, '0'))

// Partial year/month/day -> full ISO date, or null if the year itself is empty (an
// open-ended bound). Month/day default to the start of the year for "from" and the
// end of the year for "to" once a year is given; "to"'s day default is calendar-aware
// (Date's day-0-of-next-month trick) so e.g. February resolves to the 28th/29th, not a
// literal (and invalid) 31st.
function resolveBound(year: string, month: string, day: string, boundary: 'from' | 'to'): string | null {
  if (!year) return null
  const month_ = month || (boundary === 'from' ? '01' : '12')
  if (day) return `${year}-${month_}-${day}`
  if (boundary === 'from') return `${year}-${month_}-01`
  const lastDay = new Date(Number(year), Number(month_), 0).getDate()
  return `${year}-${month_}-${String(lastDay).padStart(2, '0')}`
}

function handleSubmit() {
  if (props.disabled) return
  const resolvedFrom = resolveBound(fromYear.value, fromMonth.value, fromDay.value, 'from')
  const resolvedTo = resolveBound(toYear.value, toMonth.value, toDay.value, 'to')
  if (resolvedFrom && resolvedTo && resolvedFrom > resolvedTo) return
  emit('submit', resolvedFrom, resolvedTo)
}
</script>

<template>
  <form class="flex flex-wrap items-end gap-4" @submit.prevent="handleSubmit">
    <fieldset class="flex items-end gap-2">
      <legend class="mb-1 text-xs text-muted-foreground">Von (leer = von Anfang an)</legend>
      <select
        v-model="fromYear"
        :disabled="disabled"
        class="rounded-lg border border-input bg-background px-2 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
      >
        <option value="">Jahr</option>
        <option v-for="y in YEARS" :key="y" :value="y">{{ y }}</option>
      </select>
      <select
        v-model="fromMonth"
        :disabled="disabled || !fromYear"
        class="rounded-lg border border-input bg-background px-2 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
      >
        <option value="">Monat</option>
        <option v-for="m in MONTHS" :key="m" :value="m">{{ m }}</option>
      </select>
      <select
        v-model="fromDay"
        :disabled="disabled || !fromYear"
        class="rounded-lg border border-input bg-background px-2 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
      >
        <option value="">Tag</option>
        <option v-for="d in DAYS" :key="d" :value="d">{{ d }}</option>
      </select>
    </fieldset>

    <fieldset class="flex items-end gap-2">
      <legend class="mb-1 text-xs text-muted-foreground">Bis (leer = ohne Enddatum)</legend>
      <select
        v-model="toYear"
        :disabled="disabled"
        class="rounded-lg border border-input bg-background px-2 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
      >
        <option value="">Jahr</option>
        <option v-for="y in YEARS" :key="y" :value="y">{{ y }}</option>
      </select>
      <select
        v-model="toMonth"
        :disabled="disabled || !toYear"
        class="rounded-lg border border-input bg-background px-2 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
      >
        <option value="">Monat</option>
        <option v-for="m in MONTHS" :key="m" :value="m">{{ m }}</option>
      </select>
      <select
        v-model="toDay"
        :disabled="disabled || !toYear"
        class="rounded-lg border border-input bg-background px-2 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
      >
        <option value="">Tag</option>
        <option v-for="d in DAYS" :key="d" :value="d">{{ d }}</option>
      </select>
    </fieldset>

    <button
      type="submit"
      :disabled="disabled"
      class="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
    >
      Anwenden
    </button>
  </form>
</template>
