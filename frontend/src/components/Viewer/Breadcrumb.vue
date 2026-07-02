<template>
  <nav v-if="items.length" class="breadcrumb" aria-label="문서 경로">
    <template v-for="(item, i) in items" :key="i">
      <span v-if="item.type === 'ellipsis'" class="crumb-ellipsis">…</span>
      <button
        v-else-if="!item.isFile"
        type="button"
        class="crumb-btn"
        @click="onSegmentClick(item.fullPath)"
      >{{ item.label }}</button>
      <span v-else class="crumb-current">{{ item.label }}</span>
      <span v-if="i < items.length - 1" class="crumb-sep">/</span>
    </template>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTreeReveal } from '../../composables/useTreeReveal'

const props = defineProps<{ path: string }>()
const emit = defineEmits<{ 'select-segment': [path: string] }>()
const { reveal } = useTreeReveal()

function onSegmentClick(fullPath: string) {
  // 어떤 세그먼트를 클릭하든 항상 현재 파일까지의 전체 경로를 공개(reveal)한다.
  // 클릭한 세그먼트가 이미 펼쳐져 있는 폴더인 경우가 많아 그것만으로는 아무
  // 시각적 변화가 없을 수 있으므로, 실제 파일까지 스크롤+강조해 "여기 있다"는
  // 신호를 항상 명확하게 준다. 조상 폴더는 useTreeReveal/TreeNode가 경로
  // prefix 매칭으로 알아서 함께 펼친다.
  reveal(props.path)
  emit('select-segment', fullPath)
}

interface Segment {
  type: 'segment'
  label: string
  fullPath: string
  isFile: boolean
}
type DisplayItem = Segment | { type: 'ellipsis' }

const MAX_VISIBLE_SEGMENTS = 4

const segments = computed<Segment[]>(() => {
  const parts = props.path.split('/').filter(Boolean)
  return parts.map((label, i) => ({
    type: 'segment' as const,
    label,
    fullPath: parts.slice(0, i + 1).join('/'),
    isFile: i === parts.length - 1,
  }))
})

const items = computed<DisplayItem[]>(() => {
  const all = segments.value
  if (all.length <= MAX_VISIBLE_SEGMENTS) return all
  return [all[0], { type: 'ellipsis' }, ...all.slice(-2)]
})
</script>

<style scoped>
.breadcrumb {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 0.25rem;
  font-size: 0.75rem;
  color: #6b7280;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
}
.crumb-btn {
  background: none;
  border: none;
  padding: 0.1rem 0.3rem;
  border-radius: 4px;
  color: inherit;
  cursor: pointer;
  font: inherit;
}
.crumb-btn:hover,
.crumb-btn:focus-visible {
  color: #3b82f6;
  background: rgba(59, 130, 246, 0.1);
}
.crumb-current {
  padding: 0.1rem 0.3rem;
  font-weight: 600;
}
:root.dark .crumb-current {
  color: #e5e7eb;
}
:root:not(.dark) .crumb-current {
  color: #1f2937;
}
.crumb-ellipsis {
  padding: 0 0.15rem;
  opacity: 0.6;
}
.crumb-sep {
  opacity: 0.5;
}
</style>
