<template>
  <div
    class="viewer-pane relative flex flex-col h-full min-w-0 border-2 rounded transition-colors"
    :class="isActive ? paneBorderClass : 'border-transparent'"
    @click="activate"
    @focusin="activate"
  >
    <div class="viewer-pane-toolbar absolute top-2 right-2 z-10 flex items-center gap-1.5">
      <button
        type="button"
        class="pane-toolbar-btn"
        :disabled="!canGoBack(paneId)"
        :title="t('viewer.pane.backTitle')"
        @click.stop="goBack(paneId)"
      >←</button>
      <button
        type="button"
        class="pane-toolbar-btn"
        :disabled="!canGoForward(paneId)"
        :title="t('viewer.pane.forwardTitle')"
        @click.stop="goForward(paneId)"
      >→</button>
      <span ref="colorPickerWrapperRef" class="relative inline-block">
        <button
          type="button"
          class="block w-2.5 h-2.5 rounded-full cursor-pointer"
          :class="paneBgClass"
          :title="t('viewer.pane.changeColorTitle', { paneId })"
          @click.stop="showColorPicker = !showColorPicker"
        />
        <div v-if="showColorPicker" class="pane-color-picker absolute right-0 top-full mt-1.5 flex gap-1 p-1.5 rounded-lg shadow-lg" @click.stop>
          <button
            v-for="c in colorOptions"
            :key="c"
            type="button"
            class="w-4 h-4 rounded-full cursor-pointer"
            :class="[paneColorClass(c, 'bg'), c === colorOf(paneId) ? 'pane-color-swatch-selected' : '']"
            :title="c"
            @click="selectColor(c)"
          />
        </div>
      </span>
      <button
        v-if="showAddButton"
        type="button"
        class="pane-toolbar-btn"
        :title="t('viewer.pane.splitViewTitle')"
        @click.stop="addPane()"
      >⧉ {{ t('viewer.pane.splitView') }}</button>
      <button
        v-if="showCloseButton"
        type="button"
        class="pane-toolbar-btn"
        :title="t('viewer.pane.closeTitle')"
        @click.stop="closePane(paneId)"
      >✕</button>
    </div>
    <ReadingProgressBar v-if="pane.sourceId && pane.filePath" :container="() => scrollRef" :color="colorOf(paneId)" />
    <div ref="scrollRef" class="viewer-pane-scroll flex-1 overflow-y-auto min-h-0">
      <MarkdownViewer
        v-if="pane.sourceId && pane.filePath"
        :pane-id="paneId"
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
import { useI18n } from 'vue-i18n'
import { onClickOutside } from '@vueuse/core'
import type { PaneColor, PaneId } from '../../types'
import { usePanes, paneColorClass, PANE_COLOR_OPTIONS } from '../../composables/usePanes'
import MarkdownViewer from './MarkdownViewer.vue'
import EmptyState from './EmptyState.vue'
import ReadingProgressBar from './ReadingProgressBar.vue'

const props = defineProps<{ paneId: PaneId }>()

const { t } = useI18n()
const {
  panes,
  activePaneId,
  colorOf,
  setPaneColor,
  setActivePane,
  setPaneDocument,
  canAddPane,
  addPane,
  closePane,
  canGoBack,
  canGoForward,
  goBack,
  goForward,
} = usePanes()

const pane = computed(() => panes.value.find((p) => p.id === props.paneId)!)
const isActive = computed(() => activePaneId.value === props.paneId)
const paneBorderClass = computed(() => paneColorClass(colorOf(props.paneId), 'border'))
const paneBgClass = computed(() => paneColorClass(colorOf(props.paneId), 'bg'))
const showAddButton = computed(() => panes.value.length === 1 && canAddPane())
const showCloseButton = computed(() => panes.value.length > 1)

const scrollRef = ref<HTMLElement | null>(null)

const colorOptions = PANE_COLOR_OPTIONS
const showColorPicker = ref(false)
const colorPickerWrapperRef = ref<HTMLElement | null>(null)
onClickOutside(colorPickerWrapperRef, () => { showColorPicker.value = false })

function selectColor(color: PaneColor) {
  setPaneColor(props.paneId, color)
  showColorPicker.value = false
}

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
.pane-toolbar-btn:disabled {
  opacity: 0.35;
  cursor: default;
}
.pane-toolbar-btn:disabled:hover {
  color: #9ca3af;
  border-color: rgba(148, 163, 184, 0.4);
}
.pane-color-picker {
  background: white;
  border: 1px solid rgba(148, 163, 184, 0.4);
}
:root.dark .pane-color-picker {
  background: #111827;
}
.pane-color-swatch-selected {
  box-shadow: 0 0 0 2px white, 0 0 0 3.5px rgba(107, 114, 128, 0.8);
}
:root.dark .pane-color-swatch-selected {
  box-shadow: 0 0 0 2px #111827, 0 0 0 3.5px rgba(209, 213, 219, 0.8);
}
</style>
