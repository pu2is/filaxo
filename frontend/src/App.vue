<script setup lang="ts">
import ChatPanel from '@/features/chat/components/ChatPanel.vue'
import type { ChatResponse, ChoiceItem } from '@/features/chat/types'

// Hardcoded mock -- same greeting shape as backend/modules/chat/service.py's
// _greet() response (see #17). Proves rendering end-to-end before #20 wires
// this panel up to a real POST /api/chat call.
const mockResponse: ChatResponse = {
  session_id: 'mock-session',
  bot_message:
    'Guten Tag! Ich bin Ihr CRM-Assistent für FilaksOne.\nWas möchten Sie heute analysieren?',
  choices: [
    { id: 'LEAD', label: 'Verkauf & Leads' },
    { id: 'CUSTOMER', label: 'Kunden & Adressen' },
  ],
  suggestions: [],
  show_input: true,
  result: null,
}

function handleChoice(choice: ChoiceItem) {
  console.log('choice selected:', choice)
}

function handleSubmit(text: string) {
  console.log('query submitted:', text)
}
</script>

<template>
  <div class="h-screen w-full">
    <ChatPanel :response="mockResponse" @choice="handleChoice" @submit="handleSubmit" />
  </div>
</template>
