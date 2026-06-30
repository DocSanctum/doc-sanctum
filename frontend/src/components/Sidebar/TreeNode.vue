<template>
  <ul class="pl-3">
    <li v-if="node.is_dir">
      <button
        class="flex items-center gap-1 text-xs text-gray-300 hover:text-white w-full text-left py-0.5"
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
          @select-file="$emit('select-file', $event)"
        />
      </div>
    </li>
    <li v-else>
      <button
        class="text-xs w-full text-left py-0.5 px-1 rounded truncate"
        :class="selectedPath === node.path ? 'bg-blue-600 text-white' : 'text-gray-300 hover:text-white hover:bg-gray-700'"
        @click="$emit('select-file', node.path)"
      >
        {{ node.name }}
      </button>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { TreeNode as TreeNodeType } from '../../types'

defineProps<{ node: TreeNodeType; selectedPath: string | null }>()
defineEmits<{ 'select-file': [path: string] }>()

const open = ref(true)
</script>
