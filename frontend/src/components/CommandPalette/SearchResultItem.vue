<template>
  <button
    type="button"
    class="w-full text-left px-3 py-2 rounded-md transition-colors"
    :class="active
      ? 'bg-blue-500/15 dark:bg-blue-400/20'
      : 'hover:bg-gray-100 dark:hover:bg-gray-700'"
    @click="$emit('select')"
    @mouseenter="$emit('hover')"
  >
    <div class="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mb-1">
      <span class="shrink-0 px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200">{{ match.source_name }}</span>
      <span class="truncate">{{ match.path }}</span>
      <span class="shrink-0">:{{ match.line_number }}</span>
    </div>
    <pre class="text-xs font-mono whitespace-pre-wrap break-all leading-snug"><span
      v-for="(line, i) in match.context"
      :key="i"
      :class="line === match.line ? 'text-gray-900 dark:text-white font-semibold' : 'text-gray-500 dark:text-gray-400'"
    >{{ line }}<br /></span></pre>
  </button>
</template>

<script setup lang="ts">
import type { SearchMatch } from '../../types'

defineProps<{ match: SearchMatch; active?: boolean }>()
defineEmits<{ select: []; hover: [] }>()
</script>
