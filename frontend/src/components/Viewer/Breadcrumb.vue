<template>
  <nav v-if="items.length" class="breadcrumb" :aria-label="t('viewer.breadcrumb.ariaLabel')">
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
    <button
      type="button"
      class="crumb-copy-btn"
      :class="{ 'copy-ok': copied, 'copy-fail': copyFailed }"
      :title="copyTitle"
      :aria-label="copyTitle"
      @click="copyAbsolutePath"
    >
      <svg v-if="copied" viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10.5 8 14.5 16 6" /></svg>
      <svg v-else viewBox="0 0 20 20" aria-hidden="true">
        <rect x="7" y="7" width="9" height="10" rx="1.5" />
        <path d="M13 4.5H5.5A1.5 1.5 0 0 0 4 6v7.5" />
      </svg>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useClipboard } from '@vueuse/core'
import { useTreeReveal } from '../../composables/useTreeReveal'

const props = defineProps<{ path: string; sourceRoot?: string }>()
const emit = defineEmits<{ 'select-segment': [path: string] }>()
const { t } = useI18n()
const { reveal } = useTreeReveal()
const { copy, copied, isSupported: clipboardSupported } = useClipboard({ legacy: true, copiedDuring: 1500 })
const copyFailed = ref(false)

// The source root is the registered source's own location: an absolute
// filesystem path for local sources, a repository/base URL for remote ones.
const absolutePath = computed(() =>
  props.sourceRoot ? `${props.sourceRoot.replace(/\/+$/, '')}/${props.path}` : props.path
)

// Quote only when the path needs it, so an ordinary path stays paste-able
// anywhere; `!` forces single quotes because history expansion fires in "…".
function quoteForShell(path: string): string {
  if (/^[A-Za-z0-9_@%+=:,./-]+$/.test(path)) return path
  if (path.includes('!')) return `'${path.replace(/'/g, `'\\''`)}'`
  return `"${path.replace(/(["\\$`])/g, '\\$1')}"`
}

const copyTitle = computed(() => {
  if (copied.value) return t('common.copied')
  if (copyFailed.value) return t('common.copyFailed')
  return t('viewer.breadcrumb.copyPath')
})

async function copyAbsolutePath() {
  copyFailed.value = false
  if (!clipboardSupported.value) {
    flashFailure()
    return
  }
  try {
    await copy(quoteForShell(absolutePath.value))
  } catch {
    flashFailure()
  }
}

function flashFailure() {
  copyFailed.value = true
  window.setTimeout(() => { copyFailed.value = false }, 1500)
}

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
.crumb-copy-btn {
  display: inline-flex;
  align-items: center;
  margin-left: 0.15rem;
  padding: 0.15rem;
  background: none;
  border: none;
  border-radius: 4px;
  color: inherit;
  cursor: pointer;
  opacity: 0.6;
}
.crumb-copy-btn svg {
  width: 0.9rem;
  height: 0.9rem;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.6;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.crumb-copy-btn:hover,
.crumb-copy-btn:focus-visible {
  color: #3b82f6;
  background: rgba(59, 130, 246, 0.1);
  opacity: 1;
}
.crumb-copy-btn.copy-ok {
  color: #10b981;
  opacity: 1;
}
.crumb-copy-btn.copy-fail {
  color: #ef4444;
  opacity: 1;
}
</style>
