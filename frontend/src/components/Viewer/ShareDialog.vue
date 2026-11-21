<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" @click.self="$emit('close')">
    <div class="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-md shadow-xl" role="dialog" aria-modal="true">
      <h2 class="text-gray-900 dark:text-white font-semibold mb-1">{{ t('share.dialog.title') }}</h2>
      <p class="text-xs text-gray-500 dark:text-gray-400 mb-4 break-all">{{ path }}</p>

      <p v-if="!remoteReachable" class="text-xs text-amber-600 dark:text-amber-400 mb-3">
        {{ t('share.notReachable') }}
      </p>

      <template v-if="!created">
        <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1" for="share-label">
          {{ t('share.dialog.labelField') }} <span class="opacity-70">{{ t('common.optional') }}</span>
        </label>
        <input
          id="share-label"
          ref="labelInput"
          v-model="label"
          type="text"
          maxlength="200"
          :placeholder="t('share.dialog.labelPlaceholder')"
          class="w-full text-sm bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-900 dark:text-white rounded px-3 py-2 outline-none focus:ring-1 focus:ring-blue-500 mb-2"
          @keydown.enter="submit"
        />
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-4">{{ t('share.dialog.scopeHint') }}</p>
        <p v-if="error" class="text-xs text-red-500 mb-3">{{ error }}</p>
        <div class="flex gap-2 justify-end">
          <button type="button" class="btn-secondary" @click="$emit('close')">{{ t('common.cancel') }}</button>
          <button type="button" class="btn-primary" :disabled="create.isPending.value" @click="submit">
            {{ create.isPending.value ? t('share.dialog.creating') : t('share.dialog.create') }}
          </button>
        </div>
      </template>

      <template v-else>
        <div class="flex items-center gap-2 mb-2">
          <code class="flex-1 text-xs bg-gray-100 dark:bg-gray-900 rounded px-2 py-2 text-gray-700 dark:text-gray-300 truncate font-mono">{{ createdUrl }}</code>
          <button
            type="button"
            class="text-xs px-2 py-2 rounded border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 shrink-0"
            @click="copyLink"
          >{{ copied ? `✓ ${t('common.copied')}` : t('common.copy') }}</button>
        </div>
        <p v-if="baseUrlIsPlaceholder" class="text-xs text-amber-600 dark:text-amber-400 mb-2">
          {{ t('share.placeholderWarning') }}
        </p>
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-4">{{ t('share.dialog.manageHint') }}</p>
        <div class="flex justify-end">
          <button type="button" class="btn-primary" @click="$emit('close')">{{ t('share.dialog.done') }}</button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useClipboard, onKeyStroke } from '@vueuse/core'
import { useShareLinks } from '../../composables/useShareLinks'
import type { ShareLink } from '../../types'

const props = defineProps<{ sourceId: string; path: string }>()
const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()
const { create, linkFor, baseUrlIsPlaceholder, remoteReachable } = useShareLinks()
const { copy, copied } = useClipboard({ legacy: true, copiedDuring: 1500 })

const label = ref('')
const error = ref('')
const created = ref<ShareLink | null>(null)
const labelInput = ref<HTMLInputElement | null>(null)
const createdUrl = computed(() => (created.value ? linkFor(created.value.token) : ''))

onMounted(() => labelInput.value?.focus())
onKeyStroke('Escape', () => emit('close'))

async function submit() {
  if (create.isPending.value) return
  error.value = ''
  try {
    created.value = await create.mutateAsync({
      sourceId: props.sourceId,
      path: props.path,
      label: label.value.trim() || undefined,
    })
    await copy(createdUrl.value).catch(() => undefined)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

function copyLink() {
  copy(createdUrl.value).catch(() => undefined)
}
</script>
