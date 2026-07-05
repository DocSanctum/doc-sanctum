<template>
  <div class="source-list">
    <div v-if="sourcesQuery.isPending.value" class="text-sm text-gray-400 px-3 py-2">로딩 중...</div>
    <div v-else-if="sourcesQuery.isError.value" class="text-sm text-red-400 px-3 py-2">소스 로드 실패</div>
    <ul v-else>
      <li
        v-for="source in sourcesQuery.data.value"
        :key="source.id"
        class="flex items-center justify-between px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer rounded"
        :class="{ 'bg-gray-100 dark:bg-gray-700': selectedSourceId === source.id }"
        @click="$emit('select-source', source.id)"
      >
        <span class="flex items-center gap-2 min-w-0 flex-1">
          <span
            class="inline-block w-2 h-2 rounded-full shrink-0"
            :class="statusDot(source.status)"
            :title="source.error_message ?? source.status"
          />
          <span class="flex flex-col min-w-0">
            <span class="text-sm truncate">{{ source.name }}</span>
            <span class="text-xs text-gray-400 dark:text-gray-500 truncate">{{ source.path }}</span>
          </span>
        </span>
        <button
          v-if="source.type !== 'local' && source.status !== 'syncing'"
          class="text-xs text-gray-400 hover:text-white ml-2 shrink-0"
          @click.stop="$emit('refresh-source', source.id)"
        >↻</button>
        <button
          class="text-xs text-gray-400 hover:text-red-400 ml-1 shrink-0"
          @click.stop="$emit('delete-source', source.id)"
        >✕</button>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import type { SourceStatus } from '../../types'
import { useSources } from '../../composables/useSources'

defineProps<{ selectedSourceId: string | null }>()
defineEmits<{
  'select-source': [id: string]
  'refresh-source': [id: string]
  'delete-source': [id: string]
}>()

const { sourcesQuery } = useSources()

function statusDot(status: SourceStatus): string {
  return {
    active: 'bg-green-500',
    syncing: 'bg-yellow-400 animate-pulse',
    error: 'bg-red-500',
  }[status] ?? 'bg-gray-500'
}
</script>
