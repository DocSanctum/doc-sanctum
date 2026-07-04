<template>
  <div
    class="viewer-pane relative flex flex-col h-full min-w-0 border-2 rounded transition-colors"
    :class="isActive ? paneBorderClass : 'border-transparent'"
    @click="activate"
    @focusin="activate"
  >
    <div class="viewer-pane-toolbar absolute top-2 right-2 z-10 flex items-center gap-1.5">
      <span class="inline-block w-2.5 h-2.5 rounded-full" :class="paneBgClass" :title="`패널 ${paneId} 색상`" />
      <button
        v-if="showAddButton"
        type="button"
        class="pane-toolbar-btn"
        title="분할 보기 켜기"
        @click.stop="addPane()"
      >⧉ 분할 보기</button>
      <button
        v-if="showCloseButton"
        type="button"
        class="pane-toolbar-btn"
        title="패널 닫기"
        @click.stop="closePane(paneId)"
      >✕</button>
    </div>
    <div ref="scrollRef" class="viewer-pane-scroll flex-1 overflow-y-auto min-h-0">
      <ReadingProgressBar v-if="pane.sourceId && pane.filePath" :container="() => scrollRef" />
      <MarkdownViewer
        v-if="pane.sourceId && pane.filePath"
        :source-id="pane.sourceId"
        :file-path="pane.filePath"
        :active="isActive"
        @navigate="onNavigate"
      />
      <EmptyState v-else />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { PaneId } from '../../types'
import { usePanes, paneColorClass } from '../../composables/usePanes'
import MarkdownViewer from './MarkdownViewer.vue'
import EmptyState from './EmptyState.vue'
import ReadingProgressBar from './ReadingProgressBar.vue'

const props = defineProps<{ paneId: PaneId }>()

const { panes, activePaneId, colorOf, setActivePane, setPaneDocument, canAddPane, addPane, closePane } = usePanes()

const pane = computed(() => panes.value.find((p) => p.id === props.paneId)!)
const isActive = computed(() => activePaneId.value === props.paneId)
const paneBorderClass = computed(() => paneColorClass(colorOf(props.paneId), 'border'))
const paneBgClass = computed(() => paneColorClass(colorOf(props.paneId), 'bg'))
const showAddButton = computed(() => panes.value.length === 1 && canAddPane())
const showCloseButton = computed(() => panes.value.length > 1)

const scrollRef = ref<HTMLElement | null>(null)

function activate() {
  setActivePane(props.paneId)
}

function onNavigate(path: string) {
  const current = pane.value
  if (!current.sourceId || !current.filePath) return
  const dir = current.filePath.split('/').slice(0, -1).join('/')
  const resolved = dir ? `${dir}/${path}` : path
  setPaneDocument(props.paneId, current.sourceId, resolved)
}
</script>

<style scoped>
.pane-toolbar-btn {
  font-size: 0.7rem;
  color: #9ca3af;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.4);
  cursor: pointer;
  padding: 0.15rem 0.45rem;
  border-radius: 6px;
}
:root.dark .pane-toolbar-btn {
  background: rgba(17, 24, 39, 0.6);
}
.pane-toolbar-btn:hover,
.pane-toolbar-btn:focus-visible {
  color: #3b82f6;
  border-color: #3b82f6;
}
</style>
