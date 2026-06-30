<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-gray-800 rounded-lg p-6 w-96 shadow-xl">
      <h2 class="text-white font-semibold mb-4">소스 경로 추가</h2>
      <form @submit.prevent="submit">
        <div class="mb-3">
          <label class="text-xs text-gray-300 block mb-1">이름 (선택)</label>
          <input v-model="form.name" class="input" placeholder="My Docs" />
        </div>
        <div class="mb-3">
          <label class="text-xs text-gray-300 block mb-1">유형 <span class="text-red-400">*</span></label>
          <select v-model="form.type" class="input">
            <option value="local">로컬 폴더</option>
            <option value="github">GitHub 저장소</option>
            <option value="http">HTTP/HTTPS URL</option>
            <option value="localhost">Localhost URL</option>
          </select>
        </div>
        <div class="mb-3">
          <label class="text-xs text-gray-300 block mb-1">경로 / URL <span class="text-red-400">*</span></label>
          <input v-model="form.path" class="input" :placeholder="pathPlaceholder" required />
        </div>
        <div v-if="form.type !== 'local'" class="mb-3">
          <label class="text-xs text-gray-300 block mb-1">폴링 간격 (초)</label>
          <input v-model.number="form.polling_interval_seconds" type="number" class="input" :placeholder="defaultPoll.toString()" min="30" />
        </div>
        <p v-if="error" class="text-red-400 text-xs mb-3">{{ error }}</p>
        <div class="flex gap-2 justify-end">
          <button type="button" class="btn-secondary" @click="$emit('close')">취소</button>
          <button type="submit" class="btn-primary" :disabled="loading">
            {{ loading ? '등록 중...' : '등록' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useSources } from '../../composables/useSources'
import type { SourceType } from '../../types'

defineEmits<{ close: [] }>()

const { register } = useSources()
const loading = ref(false)
const error = ref('')

const form = ref<{ name: string; type: SourceType; path: string; polling_interval_seconds: number | null }>({
  name: '',
  type: 'local',
  path: '',
  polling_interval_seconds: null,
})

const defaultPoll = computed(() => ({ github: 600, http: 300, localhost: 300 }[form.value.type] ?? 300))
const pathPlaceholder = computed(() => ({
  local: '/Users/alice/documents',
  github: 'https://github.com/owner/repo',
  http: 'https://example.com/docs',
  localhost: 'http://localhost:9090',
}[form.value.type]))

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await register.mutateAsync({
      name: form.value.name || undefined,
      type: form.value.type,
      path: form.value.path,
      polling_interval_seconds: form.value.polling_interval_seconds ?? undefined,
    })
    emit('close')
  } catch (e: any) {
    error.value = e.message ?? '등록 실패'
  } finally {
    loading.value = false
  }
}

const emit = defineEmits<{ close: [] }>()
</script>
