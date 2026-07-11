<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="!loading && $emit('close')">
    <div class="bg-white dark:bg-gray-800 rounded-lg p-6 w-96 shadow-xl">
      <h2 class="text-gray-900 dark:text-white font-semibold mb-4">{{ t('sidebar.addSourceModal.title') }}</h2>
      <form @submit.prevent="submit">
        <div class="mb-3">
          <label class="text-xs text-gray-600 dark:text-gray-300 block mb-1">{{ t('sidebar.addSourceModal.name') }} {{ t('common.optional') }}</label>
          <input v-model="form.name" class="input" placeholder="My Docs" />
        </div>
        <div class="mb-3">
          <label class="text-xs text-gray-600 dark:text-gray-300 block mb-1">{{ t('sidebar.addSourceModal.icon') }} {{ t('common.optional') }}</label>
          <IconPicker v-model="form.icon" :options="SOURCE_ICON_OPTIONS" />
        </div>
        <div class="mb-3">
          <label class="text-xs text-gray-600 dark:text-gray-300 block mb-1">{{ t('sidebar.addSourceModal.type') }} <span class="text-red-400">*</span></label>
          <select v-model="form.type" class="input">
            <option v-if="!isScaleout" value="local">{{ t('sidebar.addSourceModal.typeLocal') }}</option>
            <option value="github">{{ t('sidebar.addSourceModal.typeGithub') }}</option>
            <option value="gitlab">{{ t('sidebar.addSourceModal.typeGitlab') }}</option>
          </select>
        </div>
        <div class="mb-3">
          <label class="text-xs text-gray-600 dark:text-gray-300 block mb-1">{{ t('sidebar.addSourceModal.path') }} <span class="text-red-400">*</span></label>
          <input v-model="form.path" class="input" :placeholder="pathPlaceholder" required />
        </div>
        <div v-if="form.type !== 'local'" class="mb-3">
          <label class="text-xs text-gray-600 dark:text-gray-300 block mb-1">{{ t('sidebar.addSourceModal.pollInterval') }}</label>
          <input v-model.number="form.polling_interval_seconds" type="number" class="input" :placeholder="defaultPoll.toString()" min="30" />
        </div>
        <div v-if="form.type === 'github' || form.type === 'gitlab'" class="mb-3">
          <label class="text-xs text-gray-600 dark:text-gray-300 block mb-1">{{ t('sidebar.addSourceModal.accessToken') }} {{ t('common.optional') }}</label>
          <input v-model="form.access_token" type="password" autocomplete="off" class="input" :placeholder="t('sidebar.addSourceModal.accessTokenPlaceholder')" />
        </div>
        <p v-if="error" class="text-red-400 text-xs mb-3">{{ error }}</p>
        <div class="flex gap-2 justify-end">
          <button type="button" class="btn-secondary" :disabled="loading" @click="$emit('close')">{{ t('common.cancel') }}</button>
          <button type="submit" class="btn-primary" :disabled="loading">
            {{ loading ? t('common.registering') : t('common.register') }}
          </button>
        </div>
        <p v-if="loading && form.type !== 'local'" class="text-gray-400 text-xs mt-2">
          {{ t('sidebar.addSourceModal.indexingNotice') }}
        </p>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSources, SOURCE_ICON_OPTIONS } from '../../composables/useSources'
import { useDeploymentMode } from '../../composables/useDeploymentMode'
import IconPicker from './IconPicker.vue'
import type { SourceIcon, SourceType } from '../../types'

const { t } = useI18n()
const { register } = useSources()
const deploymentQuery = useDeploymentMode()
// scaleout backend replicas can't reach the operator's local filesystem, so
// local source registration is rejected server-side too (FR-004) — hide it
// here rather than let users hit a 422 (FR-007, specs/004-scaleout-deployment).
const isScaleout = computed(() => deploymentQuery.data.value?.mode === 'scaleout')
const loading = ref(false)
const error = ref('')

const form = ref<{ name: string; type: SourceType; path: string; polling_interval_seconds: number | null; icon: SourceIcon | null; access_token: string }>({
  name: '',
  type: 'local',
  path: '',
  polling_interval_seconds: null,
  icon: null,
  access_token: '',
})

watch(isScaleout, (scaleout) => {
  if (scaleout && form.value.type === 'local') {
    form.value.type = 'github'
  }
})

const defaultPoll = computed(() => ({ local: 300, github: 600, gitlab: 600 }[form.value.type as 'local' | 'github' | 'gitlab']))
const pathPlaceholder = computed(() => ({
  local: '/Users/alice/documents',
  github: 'https://github.com/owner/repo',
  gitlab: 'https://gitlab.com/group/project',
}[form.value.type as 'local' | 'github' | 'gitlab']))

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await register.mutateAsync({
      name: form.value.name || undefined,
      type: form.value.type,
      path: form.value.path,
      polling_interval_seconds: form.value.polling_interval_seconds ?? undefined,
      icon: form.value.icon ?? undefined,
      access_token: form.value.access_token || undefined,
    })
    emit('close')
  } catch (e: any) {
    error.value = e.message ?? t('sidebar.addSourceModal.registerFailed')
  } finally {
    loading.value = false
  }
}

const emit = defineEmits<{ close: [] }>()
</script>
