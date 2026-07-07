<template>
  <div class="file-tree">
    <div v-if="treeQuery.isPending.value" class="text-xs text-gray-400 px-3 py-1">{{ t('sidebar.fileTree.loading') }}</div>
    <div v-else-if="treeQuery.isError.value" class="text-xs text-red-400 px-3 py-1">
      {{ t('sidebar.fileTree.loadError') }}
      <button class="underline ml-1" @click="treeQuery.refetch()">{{ t('common.retry') }}</button>
    </div>
    <TreeNode
      v-else-if="treeQuery.data.value"
      :node="treeQuery.data.value.root"
      :source-id="sourceId!"
      :reveal-path="revealPath"
      :reveal-token="revealToken"
      @select-file="$emit('select-file', sourceId!, $event)"
    />
    <div v-else class="text-xs text-gray-400 px-3 py-1">{{ t('sidebar.fileTree.empty') }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useFileTree } from '../../composables/useFileTree'
import { useSSE } from '../../composables/useSSE'
import { useTreeReveal } from '../../composables/useTreeReveal'
import TreeNode from './TreeNode.vue'

const props = defineProps<{
  sourceId: string | null
}>()

defineEmits<{ 'select-file': [sourceId: string, path: string] }>()

const { t } = useI18n()
const sourceIdRef = computed(() => props.sourceId)
const { treeQuery } = useFileTree(sourceIdRef)
useSSE(sourceIdRef)
const { revealPath, revealToken } = useTreeReveal()
</script>
