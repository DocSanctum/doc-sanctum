<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="!loading && $emit('close')">
    <div class="bg-white dark:bg-gray-800 rounded-lg p-6 w-96 shadow-xl">
      <h2 class="text-gray-900 dark:text-white font-semibold mb-4">소스 경로 추가</h2>
      <form @submit.prevent="submit">
        <div class="mb-3">
          <label class="text-xs text-gray-600 dark:text-gray-300 block mb-1">이름 (선택)</label>
          <input v-model="form.name" class="input" placeholder="My Docs" />
        </div>
        <div class="mb-3">
          <label class="text-xs text-gray-600 dark:text-gray-300 block mb-1">유형 <span class="text-red-400">*</span></label>
          <select v-model="form.type" class="input">
            <option v-if="!isScaleout" value="local">로컬 폴더</option>
            <option value="github">GitHub 저장소</option>
          </select>
        </div>
        <div class="mb-3">
          <label class="text-xs text-gray-600 dark:text-gray-300 block mb-1">경로 / URL <span class="text-red-400">*</span></label>
          <input v-model="form.path" class="input" :placeholder="pathPlaceholder" required />
        </div>
        <div v-if="form.type !== 'local'" class="mb-3">
          <label class="text-xs text-gray-600 dark:text-gray-300 block mb-1">폴링 간격 (초)</label>
          <input v-model.number="form.polling_interval_seconds" type="number" class="input" :placeholder="defaultPoll.toString()" min="30" />
        </div>
        <p v-if="error" class="text-red-400 text-xs mb-3">{{ error }}</p>
        <div class="flex gap-2 justify-end">
          <button type="button" class="btn-secondary" :disabled="loading" @click="$emit('close')">취소</button>
          <button type="submit" class="btn-primary" :disabled="loading">
            {{ loading ? '등록 중...' : '등록' }}
          </button>
        </div>
        <p v-if="loading && form.type !== 'local'" class="text-gray-400 text-xs mt-2">
          문서 목록을 확인하는 중입니다. 등록 후에는 목록에 바로 표시되며, 검색 색인은 백그라운드에서 계속 진행됩니다.
        </p>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useSources } from '../../composables/useSources'
import { useDeploymentMode } from '../../composables/useDeploymentMode'
import type { SourceType } from '../../types'

const { register } = useSources()
const deploymentQuery = useDeploymentMode()
// scaleout backend replicas can't reach the operator's local filesystem, so
// local source registration is rejected server-side too (FR-004) — hide it
// here rather than let users hit a 422 (FR-007, specs/004-scaleout-deployment).
const isScaleout = computed(() => deploymentQuery.data.value?.mode === 'scaleout')
const loading = ref(false)
const error = ref('')

const form = ref<{ name: string; type: SourceType; path: string; polling_interval_seconds: number | null }>({
  name: '',
  type: 'local',
  path: '',
  polling_interval_seconds: null,
})

watch(isScaleout, (scaleout) => {
  if (scaleout && form.value.type === 'local') {
    form.value.type = 'github'
  }
})

const defaultPoll = computed(() => ({ local: 300, github: 600 }[form.value.type as 'local' | 'github']))
const pathPlaceholder = computed(() => ({
  local: '/Users/alice/documents',
  github: 'https://github.com/owner/repo',
}[form.value.type as 'local' | 'github']))

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
