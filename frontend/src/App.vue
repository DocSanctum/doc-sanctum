<template>
  <div
    class="flex h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white overflow-hidden"
    @mousemove="onDrag($event); onPaneDrag($event)"
    @mouseup="stopDrag(); stopPaneDrag()"
  >
    <!-- Sidebar -->
    <aside
      class="flex flex-col border-r border-gray-200 dark:border-gray-700 shrink-0 relative bg-white dark:bg-gray-900"
      :style="{ width: sidebarWidth + 'px' }"
    >
      <div class="flex items-center justify-between px-3 py-3 border-b border-gray-200 dark:border-gray-700">
        <span class="font-semibold text-sm">DocSanctum</span>
        <button class="text-lg hover:text-blue-400" title="소스 추가" @click="showAdd = true">＋</button>
      </div>
      <div class="overflow-y-auto flex-1 py-2 sidebar-scroll">
        <SourceList
          :selected-source-id="treeSourceId"
          @select-source="selectSource"
          @delete-source="requestDelete"
          @refresh-source="refreshSource"
        />
        <div v-if="treeSourceId" class="border-t border-gray-200 dark:border-gray-700 mt-2 pt-2">
          <FileTree
            :source-id="treeSourceId"
            @select-file="selectFile"
          />
        </div>
      </div>

      <!-- Settings button -->
      <div class="border-t border-gray-200 dark:border-gray-700 px-3 py-2 shrink-0">
        <button
          class="flex items-center gap-2 w-full px-2 py-2 rounded text-sm transition-colors"
          :class="view === 'settings' || view === 'changelog'
            ? 'bg-blue-600 text-white'
            : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700'"
          @click="view = 'settings'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          설정
        </button>
      </div>

      <!-- Resize handle -->
      <div
        class="absolute top-0 right-0 w-1 h-full cursor-col-resize hover:bg-blue-500/40 transition-colors"
        @mousedown.prevent="startDrag"
      />
    </aside>

    <!-- Main area -->
    <main
      ref="mainRef"
      class="flex-1 flex overflow-auto"
      :class="{ 'select-none': dragging || paneDragging }"
    >
      <ChangelogPage v-if="view === 'changelog'" class="flex-1 overflow-y-auto" @back="view = 'settings'" />
      <SettingsPanel v-else-if="view === 'settings'" class="flex-1 overflow-y-auto" @open-changelog="view = 'changelog'" />
      <template v-else>
        <template v-for="(pane, i) in panes" :key="pane.id">
          <div
            class="flex flex-col min-w-[18rem]"
            :style="{ flexBasis: paneFlexBasis(i), flexGrow: 0, flexShrink: 0 }"
          >
            <ViewerPane :pane-id="pane.id" />
          </div>
          <div
            v-if="i === 0 && panes.length === 2"
            class="w-1 shrink-0 cursor-col-resize hover:bg-blue-500/40 transition-colors"
            @mousedown.prevent="startPaneDrag"
          />
        </template>
      </template>
    </main>

    <AddSourceModal v-if="showAdd" @close="showAdd = false" />
    <ConfirmDeleteModal
      v-if="pendingDeleteSource"
      :source-name="pendingDeleteSource.name"
      :loading="remove.isPending.value"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import SourceList from './components/Sidebar/SourceList.vue'
import FileTree from './components/Sidebar/FileTree.vue'
import AddSourceModal from './components/Sidebar/AddSourceModal.vue'
import ConfirmDeleteModal from './components/Sidebar/ConfirmDeleteModal.vue'
import SettingsPanel from './components/Settings/SettingsPanel.vue'
import ChangelogPage from './components/Settings/ChangelogPage.vue'
import ViewerPane from './components/Viewer/ViewerPane.vue'
import { useSources } from './composables/useSources'
import { usePanes } from './composables/usePanes'
import { useTreeReveal } from './composables/useTreeReveal'

const { sourcesQuery, remove } = useSources()
const { panes, activePaneId, openInActivePane, clearSource } = usePanes()
const { reveal } = useTreeReveal()

const showAdd = ref(false)
const pendingDeleteId = ref<string | null>(null)
const pendingDeleteSource = computed(() =>
  sourcesQuery.data.value?.find((s) => s.id === pendingDeleteId.value) ?? null
)
const view = ref<'viewer' | 'settings' | 'changelog'>('viewer')

// 좌측 트리는 화면에 하나만 존재하며(스펙 Assumptions), 기본적으로는 사용자가
// 사이드바에서 직접 선택한 소스를 기준으로 표시된다. 최초 로드 시에는 패널 1의
// 소스를 기준으로 초기화한다.
const treeSourceId = ref<string | null>(panes.value[0]?.sourceId ?? null)

// 분할 보기에서 다른 패널을 클릭해 활성 패널이 바뀌면, 그 패널이 어느 소스의
// 문서를 보고 있는지 트리에서 바로 확인할 수 있도록 트리를 해당 소스로 전환하고
// 그 문서 항목까지 펼쳐서 보여준다(reveal). 패널이 비어 있으면 트리는 그대로 둔다.
watch(activePaneId, (id) => {
  const pane = panes.value.find((p) => p.id === id)
  if (!pane?.sourceId || !pane.filePath) return
  treeSourceId.value = pane.sourceId
  reveal(pane.filePath)
})

const mainRef = ref<HTMLElement | null>(null)

// Sidebar resize
const SIDEBAR_MIN = 180
const SIDEBAR_MAX = 480
const sidebarWidth = ref(256)
const dragging = ref(false)

function startDrag() { dragging.value = true }
function onDrag(e: MouseEvent) {
  if (!dragging.value) return
  sidebarWidth.value = Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, e.clientX))
}
function stopDrag() { dragging.value = false }

// Pane resize (분할 보기일 때 두 패널 사이 경계 드래그, FR-009)
const PANE_MIN_RATIO = 0.2
const PANE_MAX_RATIO = 0.8
const paneSplitRatio = ref(0.5)
const paneDragging = ref(false)

function startPaneDrag() { paneDragging.value = true }
function onPaneDrag(e: MouseEvent) {
  if (!paneDragging.value || !mainRef.value) return
  const rect = mainRef.value.getBoundingClientRect()
  const ratio = (e.clientX - rect.left) / rect.width
  paneSplitRatio.value = Math.min(PANE_MAX_RATIO, Math.max(PANE_MIN_RATIO, ratio))
}
function stopPaneDrag() { paneDragging.value = false }

function paneFlexBasis(index: number): string {
  if (panes.value.length < 2) return '100%'
  const ratio = index === 0 ? paneSplitRatio.value : 1 - paneSplitRatio.value
  return `calc(${ratio * 100}% - 2px)`
}

function selectSource(id: string) {
  treeSourceId.value = id
}

function selectFile(sourceId: string, path: string) {
  treeSourceId.value = sourceId
  openInActivePane(sourceId, path)
  view.value = 'viewer'
}

function requestDelete(id: string) {
  pendingDeleteId.value = id
}

function cancelDelete() {
  pendingDeleteId.value = null
}

async function confirmDelete() {
  const id = pendingDeleteId.value
  if (!id) return
  await remove.mutateAsync(id)
  pendingDeleteId.value = null
  clearSource(id)
  if (treeSourceId.value === id) {
    treeSourceId.value = null
  }
}

async function refreshSource(id: string) {
  const { api } = await import('./services/api')
  await api.refreshSource(id)
}
</script>
