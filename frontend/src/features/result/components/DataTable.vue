<script setup lang="ts">
import { computed } from 'vue'

import type { ResultPayload } from '@/features/chat/types'

const props = defineProps<{ result: ResultPayload }>()

// MVP 1 Wave 1 (#26): a plain table, capped at 50 rows -- charts, sorting, and the
// SQL/source viewers are Big Goal 5 scope.
const MAX_ROWS = 50
const visibleRows = computed(() => props.result.rows.slice(0, MAX_ROWS))
const hiddenRowCount = computed(() => Math.max(props.result.rows.length - MAX_ROWS, 0))
</script>

<template>
  <div class="max-w-[80%] overflow-x-auto rounded-lg border border-border">
    <table class="w-full text-left text-sm">
      <thead class="bg-muted">
        <tr>
          <th v-for="column in result.columns" :key="column.name" class="whitespace-nowrap px-3 py-2 font-medium">
            {{ column.name }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in visibleRows" :key="index" class="border-t border-border">
          <td v-for="column in result.columns" :key="column.name" class="whitespace-nowrap px-3 py-2">
            {{ row[column.name] }}
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="hiddenRowCount > 0" class="border-t border-border px-3 py-2 text-xs text-muted-foreground">
      +{{ hiddenRowCount }} weitere Zeilen
    </p>
  </div>
</template>
