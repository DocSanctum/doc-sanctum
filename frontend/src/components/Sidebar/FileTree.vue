<template>
  <div class="file-tree">
    <div v-if="treeQuery.isPending.value" class="text-xs text-gray-400 px-3 py-1">파일 목록 로딩 중...</div>
    <div v-else-if="treeQuery.isError.value" class="text-xs text-red-400 px-3 py-1">
      파일 목록을 불러올 수 없습니다.
      <button class="underline ml-1" @click="treeQuery.refetch()">다시 시도</button>
    </div>
    <TreeNode
      v-else-if="treeQuery.data.value"
      :node="treeQuery.data.value.root"
      :source-id="sourceId!"
      :reveal-path="revealPath"
      :reveal-token="revealToken"
      @select-file="$emit('select-file', sourceId!, $event)"
    />
    <div v-else class="text-xs text-gray-400 px-3 py-1">MD 파일 없음</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useFileTree } from '../../composables/useFileTree'
import { useSSE } from '../../composables/useSSE'
import { useTreeReveal } from '../../composables/useTreeReveal'
import TreeNode from './TreeNode.vue'

const props = defineProps<{
  sourceId: string | null
}>()

defineEmits<{ 'select-file': [sourceId: string, path: string] }>()

const sourceIdRef = computed(() => props.sourceId)
const { treeQuery } = useFileTree(sourceIdRef)
useSSE(sourceIdRef)
const { revealPath, revealToken } = useTreeReveal()
</script>
