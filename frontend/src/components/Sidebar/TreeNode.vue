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
        :class="{ 'tree-reveal-flash': flashing }"
        @click="$emit('select-file', node.path)"
      >
        <span v-if="matches.length" class="flex items-center gap-0.5 shrink-0">
          <span
            v-for="m in matches"
            :key="m.paneId"
            class="pane-match-dot inline-block w-1.5 h-1.5 rounded-full"
            :class="paneColorClass(m.color, 'bg')"
            :title="`패널 ${m.paneId}에서 열림`"
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

const { paneMatches } = usePanes()
const matches = computed(() => paneMatches(props.sourceId, props.node.path))

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
