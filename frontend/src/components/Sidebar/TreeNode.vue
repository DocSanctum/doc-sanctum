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
          :selected-path="selectedPath"
          :reveal-path="revealPath"
          :reveal-token="revealToken"
          @select-file="$emit('select-file', $event)"
        />
      </div>
    </li>
    <li v-else>
      <button
        ref="fileBtn"
        class="text-xs w-full text-left py-0.5 px-1 rounded truncate"
        :class="[
          selectedPath === node.path ? 'bg-blue-600 text-white' : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700',
          { 'tree-reveal-flash': flashing },
        ]"
        @click="$emit('select-file', node.path)"
      >
        {{ node.name }}
      </button>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import type { TreeNode as TreeNodeType } from '../../types'

const props = defineProps<{
  node: TreeNodeType
  selectedPath: string | null
  revealPath?: string | null
  revealToken?: number
}>()
defineEmits<{ 'select-file': [path: string] }>()

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
