<template>
  <section class="mb-8">
    <h2 class="text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-1">{{ t('share.settings.label') }}</h2>
    <p class="text-xs text-gray-400 dark:text-gray-500 mb-3">{{ t('share.settings.description') }}</p>

    <p v-if="!remoteReachable" class="text-xs text-amber-600 dark:text-amber-400 mb-3">{{ t('share.notReachable') }}</p>

    <!-- Base URL -->
    <div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-3 mb-3">
      <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1" for="share-base-url">{{ t('share.settings.baseUrl') }}</label>
      <div class="flex items-center gap-2">
        <input
          id="share-base-url"
          v-model="baseUrlDraft"
          type="url"
          :placeholder="settingsQuery.data.value?.suggested_base_url || `http://192.168.0.10:${settingsQuery.data.value?.remote_port ?? 8020}`"
          class="flex-1 min-w-0 text-xs font-mono placeholder:text-gray-400 dark:placeholder:text-gray-500 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-900 dark:text-white rounded px-2 py-1.5 outline-none focus:ring-1 focus:ring-blue-500"
        />
        <button
          type="button"
          class="text-xs px-2 py-1.5 rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
          :disabled="baseUrlDraft.trim().replace(/\/+$/, '') === (settingsQuery.data.value?.base_url ?? '') || saveBaseUrl.isPending.value"
          @click="saveBaseUrl.mutate(baseUrlDraft)"
        >{{ t('common.save') }}</button>
      </div>
      <p class="text-xs mt-1.5" :class="baseUrlIsPlaceholder ? 'text-amber-600 dark:text-amber-400' : 'text-gray-400 dark:text-gray-500'">
        {{ baseUrlIsPlaceholder ? t('share.placeholderWarning') : t('share.settings.baseUrlHint', { url: baseUrl }) }}
      </p>
    </div>

    <!-- Links -->
    <div v-if="linksQuery.isLoading.value" class="text-xs text-gray-400 dark:text-gray-500">{{ t('common.loading') }}</div>
    <div v-else-if="links.length === 0" class="text-xs text-gray-400 dark:text-gray-500 italic">{{ t('share.settings.empty') }}</div>
    <div v-else class="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden divide-y divide-gray-100 dark:divide-gray-700">
      <div
        v-for="link in links"
        :key="link.id"
        class="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-2.5 bg-white dark:bg-gray-800"
      >
        <div class="flex-1 min-w-[12rem]">
          <div class="flex items-center gap-2">
            <span class="text-sm font-medium text-gray-900 dark:text-white truncate">{{ link.label || fileName(link.path) }}</span>
            <span
              v-if="link.available === false"
              class="text-[10px] px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400 shrink-0"
            >{{ t('share.settings.missing') }}</span>
          </div>
          <div class="text-xs text-gray-400 dark:text-gray-500 truncate" :title="link.path">
            {{ link.source_name ?? '?' }} · {{ link.path }}
          </div>
          <div class="text-xs text-gray-400 dark:text-gray-500">
            {{ t('share.settings.created', { date: formatDate(link.created_at) }) }} ·
            {{ link.last_accessed_at
              ? t('share.settings.lastOpened', { date: formatDate(link.last_accessed_at), count: link.access_count })
              : t('share.settings.neverOpened') }}
          </div>
        </div>
        <div class="flex items-center gap-1.5 shrink-0">
          <button
            type="button"
            class="text-xs px-2 py-1 rounded border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
            @click="copyLink(link)"
          >{{ copiedId === link.id ? `✓ ${t('common.copied')}` : t('common.copy') }}</button>
          <button
            type="button"
            class="text-xs px-2 py-1 rounded border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50"
            :disabled="revoke.isPending.value"
            @click="revokeLink(link)"
          >{{ t('share.settings.revoke') }}</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useShareLinks } from '../../composables/useShareLinks'
import type { ShareLink } from '../../types'

const { t, locale } = useI18n()
const {
  linksQuery,
  settingsQuery,
  baseUrl,
  baseUrlIsPlaceholder,
  remoteReachable,
  linkFor,
  revoke,
  saveBaseUrl,
} = useShareLinks()

const links = computed(() => linksQuery.data.value ?? [])
const baseUrlDraft = ref('')
const copiedId = ref('')

watch(
  () => settingsQuery.data.value?.base_url,
  (value) => { baseUrlDraft.value = value ?? '' },
  { immediate: true },
)

function fileName(path: string): string {
  return path.split('/').pop() ?? path
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(locale.value, { dateStyle: 'medium', timeStyle: 'short' })
}

async function copyLink(link: ShareLink) {
  await navigator.clipboard.writeText(linkFor(link.token))
  copiedId.value = link.id
  setTimeout(() => { copiedId.value = '' }, 2000)
}

function revokeLink(link: ShareLink) {
  if (!window.confirm(t('share.settings.revokeConfirm', { name: link.label || fileName(link.path) }))) return
  revoke.mutate(link.id)
}
</script>
