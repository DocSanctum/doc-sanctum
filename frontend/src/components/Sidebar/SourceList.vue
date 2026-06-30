<template>
  <div class="source-list">
    <div v-if="sourcesQuery.isPending.value" class="text-sm text-gray-400 px-3 py-2">로딩 중...</div>
    <div v-else-if="sourcesQuery.isError.value" class="text-sm text-red-400 px-3 py-2">소스 로드 실패</div>
    <ul v-else>
      <li
        v-for="source in sourcesQuery.data.value"
        :key="source.id"
        class="flex items-center justify-between px-3 py-2 hover:bg-gray-700 cursor-pointer rounded"
        :class="{ 'bg-gray-700': selectedSourceId === source.id }"
        @click="$emit('select-source', source.id)"
      >
        <span class="flex items-center gap-2 text-sm truncate">
          <span :title="source.error_message ?? ''">{{ statusIcon(source.status) }}</span>
          <span class="truncate">{{ source.name }}</span>
        </span>
        <button
          v-if="source.type !== 'local'"
          class="text-xs text-gray-400 hover:text-white ml-2 shrink-0"
          :disabled="source.status === 'syncing'"
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

function statusIcon(status: SourceStatus): string {
  return { active: '🟢', syncing: '🔄', error: '🔴' }[status] ?? '⚪'
}
</script>
