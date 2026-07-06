<script setup lang="ts">
defineProps<{ text: string }>()
</script>

<template>
  <div class="flex justify-end">
    <div
      class="max-w-[80%] whitespace-pre-line rounded-2xl rounded-br-sm bg-primary px-4 py-2 text-sm text-primary-foreground"
    >
      {{ text }}
    </div>
  </div>
</template>
