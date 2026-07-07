<script setup lang="ts">
import type { BreadcrumbItem } from '@/features/chat/types'

defineProps<{ crumbs: BreadcrumbItem[]; disabled?: boolean }>()
const emit = defineEmits<{ remove: [crumb: BreadcrumbItem] }>()
</script>

<template>
  <div v-if="crumbs.length" class="flex flex-wrap gap-2">
    <button
      v-for="crumb in crumbs"
      :key="crumb.key"
      type="button"
      :disabled="disabled"
      class="flex items-center gap-1.5 rounded-full border border-border bg-muted px-3 py-1 text-xs hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
      @click="emit('remove', crumb)"
    >
      <span>{{ crumb.label }}</span>
      <span aria-hidden="true">×</span>
    </button>
  </div>
</template>
