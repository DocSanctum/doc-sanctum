<template>
  <div class="flex flex-col items-center justify-center h-full text-gray-400 dark:text-gray-500">
    <div class="text-5xl mb-4">📄</div>
    <p class="text-sm">{{ t('viewer.emptyState') }}</p>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>
