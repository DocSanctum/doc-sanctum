<template>
  <div
    class="search-result-row w-full text-left px-3 py-2 rounded-md transition-colors cursor-pointer flex items-start gap-2"
    :class="active
      ? 'bg-blue-500/15 dark:bg-blue-400/20'
      : 'hover:bg-gray-100 dark:hover:bg-gray-700'"
    @click="$emit('select')"
    @mouseenter="$emit('hover')"
  >
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mb-1">
        <span class="shrink-0 px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200">{{ match.source_name }}</span>
        <span class="truncate">{{ match.path }}</span>
        <span class="shrink-0">:{{ match.line_number }}</span>
        <span v-if="match.page != null" class="shrink-0 px-1 rounded bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200">{{ t('search.pageLabel', { page: match.page }) }}</span>
      </div>
      <pre class="text-xs font-mono whitespace-pre-wrap break-all leading-snug"><span
        v-for="(line, i) in match.context"
        :key="i"
        :class="line === match.line ? 'text-gray-900 dark:text-white font-semibold' : 'text-gray-500 dark:text-gray-400'"
      >{{ line }}<br /></span></pre>
    </div>
    <!-- Only shown when 2+ panes are open — with a single pane there's no
         real choice to offer, so it would just be visual clutter. -->
    <div v-if="paneOptions.length > 1" class="flex items-center gap-1 shrink-0 pt-0.5">
      <span class="text-[10px] text-gray-400 dark:text-gray-500 mr-0.5">{{ t('search.openInLabel') }}</span>
      <button
        v-for="p in paneOptions"
        :key="p.id"
        type="button"
        class="w-5 h-5 rounded-full text-[10px] font-semibold leading-5 text-center text-white"
        :class="paneColorClass(p.color, 'bg')"
        :title="t('search.openInPane', { paneId: p.id })"
        @click.stop="$emit('open-in-pane', p.id)"
      >{{ p.id }}</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { paneColorClass } from '../../composables/usePanes'
import type { SearchMatch, PaneId, PaneColor } from '../../types'

withDefaults(
  defineProps<{
    match: SearchMatch
    active?: boolean
    paneOptions: { id: PaneId; color: PaneColor }[]
  }>(),
  { paneOptions: () => [] }
)
defineEmits<{ select: []; hover: []; 'open-in-pane': [paneId: PaneId] }>()

const { t } = useI18n()
</script>
