<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="!loading && $emit('close')">
    <div class="bg-white dark:bg-gray-800 rounded-lg p-6 w-96 shadow-xl">
      <h2 class="text-gray-900 dark:text-white font-semibold mb-4">{{ t('sidebar.editSourceModal.title') }}</h2>
      <form @submit.prevent="submit">
        <div class="mb-3">
          <label class="text-xs text-gray-600 dark:text-gray-300 block mb-1">{{ t('sidebar.editSourceModal.name') }}</label>
          <input v-model="form.name" class="input" placeholder="My Docs" required />
        </div>
        <div class="mb-3">
          <label class="text-xs text-gray-600 dark:text-gray-300 block mb-1">{{ t('sidebar.addSourceModal.icon') }} {{ t('common.optional') }}</label>
          <IconPicker v-model="form.icon" :options="SOURCE_ICON_OPTIONS" />
        </div>
        <p v-if="error" class="text-red-400 text-xs mb-3">{{ error }}</p>
        <div class="flex gap-2 justify-end">
          <button type="button" class="btn-secondary" :disabled="loading" @click="$emit('close')">{{ t('common.cancel') }}</button>
          <button type="submit" class="btn-primary" :disabled="loading">
            {{ loading ? t('common.saving') : t('common.save') }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSources, SOURCE_ICON_OPTIONS } from '../../composables/useSources'
import IconPicker from './IconPicker.vue'
import type { Source, SourceIcon } from '../../types'

const props = defineProps<{ source: Source }>()
const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()
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
    error.value = e.message ?? t('sidebar.editSourceModal.saveFailed')
  } finally {
    loading.value = false
  }
}
</script>
