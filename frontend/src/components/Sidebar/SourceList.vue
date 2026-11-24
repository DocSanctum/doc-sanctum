<template>
  <div class="source-list">
    <div
      v-if="sourcesQuery.isPending.value"
      class="text-sm text-gray-400 truncate"
      :class="collapsed ? 'px-1 py-2 text-center' : 'px-3 py-2'"
      :title="collapsed ? t('sidebar.sourceList.loading') : undefined"
    >{{ collapsed ? '…' : t('sidebar.sourceList.loading') }}</div>
    <div
      v-else-if="sourcesQuery.isError.value"
      class="text-sm text-red-400 truncate"
      :class="collapsed ? 'px-1 py-2 text-center' : 'px-3 py-2'"
      :title="collapsed ? t('sidebar.sourceList.loadError') : undefined"
    >{{ collapsed ? '⚠' : t('sidebar.sourceList.loadError') }}</div>
    <ul v-else-if="collapsed" class="flex flex-col items-center gap-1 px-1.5">
      <li
        v-for="source in sourcesQuery.data.value"
        :key="source.id"
        class="relative w-9 h-9 flex items-center justify-center rounded cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 shrink-0"
        :class="{ 'bg-gray-100 dark:bg-gray-700': selectedSourceId === source.id }"
        :title="source.name"
        @click="$emit('select-source', source.id)"
      >
        <span class="text-sm leading-none">{{ source.icon || source.name.charAt(0).toUpperCase() }}</span>
        <span
          class="absolute bottom-0.5 right-0.5 inline-block w-1.5 h-1.5 rounded-full"
          :class="statusDot(dotStatus(source))"
          :title="progressText(source) ?? source.error_message ?? source.status"
        />
      </li>
    </ul>
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
            :class="statusDot(dotStatus(source))"
            :title="source.error_message ?? source.status"
          />
          <span class="flex flex-col min-w-0 flex-1">
            <span class="text-sm truncate">
              <span v-if="source.icon" class="mr-1">{{ source.icon }}</span>{{ source.name }}
            </span>
            <template v-if="progressText(source)">
              <span
                class="index-progress-text flex gap-1.5 text-xs text-amber-600 dark:text-amber-400"
                :title="progressText(source) ?? undefined"
              >
                <span class="truncate">{{ t(`sidebar.sourceList.indexing.${indexProgress(source)?.reasonKey}`) }}</span>
                <span v-if="progressCount(source)" class="index-progress-count ml-auto shrink-0 tabular-nums">{{ progressCount(source) }}</span>
              </span>
              <span
                v-if="indexProgress(source)?.percent != null"
                class="mt-1 block h-0.5 w-full rounded bg-gray-200 dark:bg-gray-700 overflow-hidden"
                role="progressbar"
                :aria-valuenow="indexProgress(source)?.percent ?? 0"
                aria-valuemin="0"
                aria-valuemax="100"
              >
                <span
                  class="index-progress-bar block h-full bg-yellow-400 transition-[width] duration-500"
                  :style="{ width: `${indexProgress(source)?.percent ?? 0}%` }"
                />
              </span>
            </template>
            <span v-else class="text-xs text-gray-400 dark:text-gray-500 truncate">{{ source.path }}</span>
          </span>
        </span>
        <button
          v-if="source.type !== 'local' && source.status !== 'syncing'"
          class="text-xs text-gray-400 hover:text-white ml-2 shrink-0"
          @click.stop="$emit('refresh-source', source.id)"
        >↻</button>
        <button
          class="text-xs text-gray-400 hover:text-white ml-1 shrink-0"
          :title="t('sidebar.sourceList.editSource')"
          @click.stop="$emit('edit-source', source.id)"
        >✎</button>
        <button
          class="text-xs text-gray-400 hover:text-red-400 ml-1 shrink-0"
          @click.stop="$emit('delete-source', source.id)"
        >✕</button>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { Source, SourceStatus } from '../../types'
import { useSources } from '../../composables/useSources'
import { indexProgress, isIndexing } from '../../utils/indexProgress'

withDefaults(defineProps<{ selectedSourceId: string | null; collapsed?: boolean }>(), {
  collapsed: false,
})
defineEmits<{
  'select-source': [id: string]
  'refresh-source': [id: string]
  'edit-source': [id: string]
  'delete-source': [id: string]
}>()

const { t, locale } = useI18n()

function progressCount(source: Source): string | null {
  const progress = indexProgress(source)
  if (progress?.total == null) return null
  const format = (value: number) => value.toLocaleString(locale.value)
  return `${format(progress.done ?? 0)}/${format(progress.total)}`
}

// The full line, used for tooltips where the sidebar is too narrow.
function progressText(source: Source): string | null {
  const progress = indexProgress(source)
  if (!progress) return null
  const label = t(`sidebar.sourceList.indexing.${progress.reasonKey}`)
  const count = progressCount(source)
  return count ? `${label} · ${count}` : label
}

// A background re-index on a remote source keeps its status, so pulse anyway.
function dotStatus(source: Source): SourceStatus {
  return isIndexing(source) ? 'syncing' : source.status
}
const { sourcesQuery } = useSources()

function statusDot(status: SourceStatus): string {
  return {
    active: 'bg-green-500',
    syncing: 'bg-yellow-400 animate-pulse',
    error: 'bg-red-500',
    // Usable but incomplete (some documents failed to index) — amber, distinct
    // from a hard red error. Hovering shows the error_message summary.
    partial: 'bg-amber-500',
  }[status] ?? 'bg-gray-500'
}
</script>
