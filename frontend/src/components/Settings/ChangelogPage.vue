<template>
  <div class="max-w-3xl mx-auto px-8 py-10">
    <div class="flex items-center gap-3 mb-8">
      <button
        class="text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-white transition-colors"
        @click="$emit('back')"
      >
        {{ t('settings.changelog.back') }}
      </button>
      <h1 class="text-lg font-semibold text-gray-900 dark:text-white">{{ t('settings.changelog.allHistory') }}</h1>
    </div>

    <div class="space-y-4">
      <div
        v-for="entry in changelog"
        :key="entry.version"
        class="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden"
      >
        <div class="flex items-center justify-between px-4 py-2.5 bg-gray-50 dark:bg-gray-800">
          <div class="flex items-center gap-2">
            <span class="text-xs font-mono font-semibold text-gray-900 dark:text-white">v{{ entry.version }}</span>
            <span
              v-if="entry.version === currentVersion"
              class="text-xs px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 rounded"
            >{{ t('common.current') }}</span>
          </div>
          <span class="text-xs text-gray-400 dark:text-gray-500">{{ entry.date }}</span>
        </div>
        <ul class="px-4 py-3 space-y-1.5 bg-white dark:bg-gray-900">
          <li
            v-for="(change, i) in entry.changes"
            :key="i"
            class="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300"
          >
            <span class="text-blue-400 mt-0.5 shrink-0">·</span>
            {{ change }}
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { changelog } from '../../data/changelog'
import pkg from '../../../package.json'

defineEmits<{ back: [] }>()

const { t } = useI18n()
const currentVersion = pkg.version
</script>
