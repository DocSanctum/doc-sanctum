<template>
  <ul class="pl-3">
    <li v-if="node.is_dir">
      <button
        class="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white w-full text-left py-0.5"
        @click="open = !open"
      >
        <span>{{ open ? '▾' : '▸' }}</span>
        <span class="font-medium">{{ node.name }}</span>
      </button>
      <div v-if="open">
        <TreeNode
          v-for="child in node.children ?? []"
          :key="child.path"
          :node="child"
          :source-id="sourceId"
          :reveal-path="revealPath"
          :reveal-token="revealToken"
          @select-file="$emit('select-file', $event)"
        />
      </div>
    </li>
    <li v-else>
      <button
        ref="fileBtn"
        class="flex items-center gap-1.5 text-xs w-full text-left py-0.5 px-1 rounded truncate text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700"
        :class="[{ 'tree-reveal-flash': flashing }, activeMatchTint]"
        @click="$emit('select-file', node.path)"
      >
        <span v-if="matches.length" class="flex items-center gap-0.5 shrink-0">
          <span
            v-for="m in matches"
            :key="m.paneId"
            class="pane-match-dot inline-block rounded-full"
            :class="[paneColorClass(m.color, 'bg'), m.paneId === activePaneId ? 'w-2 h-2' : 'w-1.5 h-1.5']"
            :title="`패널 ${m.paneId}에서 열림${m.paneId === activePaneId ? ' (활성)' : ''}`"
          />
        </span>
        <span class="truncate">{{ node.name }}</span>
      </button>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import type { TreeNode as TreeNodeType } from '../../types'
import { usePanes, paneColorClass } from '../../composables/usePanes'

const props = defineProps<{
  node: TreeNodeType
  sourceId: string
  revealPath?: string | null
  revealToken?: number
}>()
defineEmits<{ 'select-file': [path: string] }>()

const { paneMatches, activePaneId } = usePanes()
const matches = computed(() => paneMatches(props.sourceId, props.node.path))
// 활성 패널에 열려 있는 문서는 트리에서도 한 번 더 눈에 띄어야, 트리 클릭이
// 어디로 반영될지 예측하기 쉽다(FR-004/FR-012 연장선) — 점 크기와 함께
// 행 배경에 옅은 색 틴트를 준다.
const activeMatch = computed(() => matches.value.find((m) => m.paneId === activePaneId.value))
const activeMatchTint = computed(() => (activeMatch.value ? paneColorClass(activeMatch.value.color, 'tint') : ''))

const open = ref(true)
const fileBtn = ref<HTMLButtonElement | null>(null)
const flashing = ref(false)

watch(
  () => props.revealToken,
  async () => {
    const target = props.revealPath
    if (!target) return

    if (props.node.is_dir) {
      if (target === props.node.path || target.startsWith(`${props.node.path}/`)) {
        open.value = true
      }
      return
    }

    if (target === props.node.path) {
      await nextTick()
      fileBtn.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      flashing.value = true
      window.setTimeout(() => {
        flashing.value = false
      }, 1200)
    }
  }
)
</script>

<style scoped>
.tree-reveal-flash {
  animation: tree-reveal-flash 1.2s ease-out;
}
@keyframes tree-reveal-flash {
  0%,
  40% {
    background-color: rgba(59, 130, 246, 0.35);
  }
  100% {
    background-color: transparent;
  }
}
</style>
