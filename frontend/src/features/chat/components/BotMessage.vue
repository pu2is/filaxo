<script setup lang="ts">
defineProps<{ message: string }>()
</script>

<template>
  <div class="flex justify-start">
    <div
      class="max-w-[80%] whitespace-pre-line rounded-2xl rounded-bl-sm bg-muted px-4 py-2 text-sm text-foreground"
    >
      {{ message }}
    </div>
  </div>
</template>
