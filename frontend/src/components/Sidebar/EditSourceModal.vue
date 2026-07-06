<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="!loading && $emit('close')">
    <div class="bg-white dark:bg-gray-800 rounded-lg p-6 w-96 shadow-xl">
      <h2 class="text-gray-900 dark:text-white font-semibold mb-4">소스 정보 수정</h2>
      <form @submit.prevent="submit">
        <div class="mb-3">
          <label class="text-xs text-gray-600 dark:text-gray-300 block mb-1">이름</label>
          <input v-model="form.name" class="input" placeholder="My Docs" required />
        </div>
        <div class="mb-3">
          <label class="text-xs text-gray-600 dark:text-gray-300 block mb-1">아이콘 (선택)</label>
          <IconPicker v-model="form.icon" :options="SOURCE_ICON_OPTIONS" />
        </div>
        <p v-if="error" class="text-red-400 text-xs mb-3">{{ error }}</p>
        <div class="flex gap-2 justify-end">
          <button type="button" class="btn-secondary" :disabled="loading" @click="$emit('close')">취소</button>
          <button type="submit" class="btn-primary" :disabled="loading">
            {{ loading ? '저장 중...' : '저장' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useSources, SOURCE_ICON_OPTIONS } from '../../composables/useSources'
import IconPicker from './IconPicker.vue'
import type { Source, SourceIcon } from '../../types'

const props = defineProps<{ source: Source }>()
const emit = defineEmits<{ close: [] }>()

const { patch } = useSources()
const loading = ref(false)
const error = ref('')

const form = ref<{ name: string; icon: SourceIcon | null }>({
  name: props.source.name,
  icon: props.source.icon,
})

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await patch.mutateAsync({
      id: props.source.id,
      data: { name: form.value.name, icon: form.value.icon },
    })
    emit('close')
  } catch (e: any) {
    error.value = e.message ?? '저장 실패'
  } finally {
    loading.value = false
  }
}
</script>
