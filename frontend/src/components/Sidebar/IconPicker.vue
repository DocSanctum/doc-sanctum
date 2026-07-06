<template>
  <div class="flex flex-wrap gap-1">
    <button
      v-for="icon in options"
      :key="icon"
      type="button"
      class="icon-option w-7 h-7 flex items-center justify-center rounded text-base"
      :class="{ 'icon-option-selected': modelValue === icon }"
      :title="icon"
      @click="$emit('update:modelValue', modelValue === icon ? null : icon)"
    >{{ icon }}</button>
  </div>
</template>

<script setup lang="ts">
import type { SourceIcon } from '../../types'

defineProps<{ modelValue: SourceIcon | null; options: SourceIcon[] }>()
defineEmits<{ 'update:modelValue': [icon: SourceIcon | null] }>()
</script>

<style scoped>
.icon-option {
  border: 1px solid transparent;
  cursor: pointer;
}
.icon-option:hover {
  background: rgba(148, 163, 184, 0.15);
}
.icon-option-selected {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.12);
}
</style>
