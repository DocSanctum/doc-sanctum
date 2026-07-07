<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="$emit('cancel')">
    <div class="bg-white dark:bg-gray-800 rounded-lg p-6 w-96 shadow-xl">
      <h2 class="text-gray-900 dark:text-white font-semibold mb-2">{{ t('sidebar.confirmDeleteModal.title') }}</h2>
      <i18n-t keypath="sidebar.confirmDeleteModal.body" tag="p" class="text-sm text-gray-600 dark:text-gray-300 mb-4">
        <template #name><span class="font-medium">{{ sourceName }}</span></template>
      </i18n-t>
      <div class="flex gap-2 justify-end">
        <button type="button" class="btn-secondary" @click="$emit('cancel')">{{ t('common.cancel') }}</button>
        <button type="button" class="btn-primary bg-red-600 hover:bg-red-700" :disabled="loading" @click="$emit('confirm')">
          {{ loading ? t('common.deleting') : t('common.delete') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

defineProps<{ sourceName: string; loading: boolean }>()
defineEmits<{ confirm: []; cancel: [] }>()

const { t } = useI18n()
</script>
