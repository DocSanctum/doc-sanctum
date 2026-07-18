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
        <span class="flex items-center gap-1.5 font-semibold text-sm">
          <svg viewBox="0 0 460 350" class="h-4 w-auto shrink-0" aria-hidden="true">
            <path d="M223.90,333.93 C200.65,317.70 183.85,308.84 163.50,302.09 C141.10,294.66 122.07,291.84 94.50,291.88 C75.32,291.91 60.93,293.41 41.99,297.36 C34.83,298.86 30.12,299.41 29.50,298.83 C28.27,297.68 28.10,62.57 29.33,61.33 C29.79,60.88 34.96,60.50 40.83,60.50 L51.50,60.50 L51.75,164.88 L52.01,269.26 L56.25,268.64 C66.18,267.17 90.08,266.78 101.50,267.90 C135.29,271.20 170.69,283.22 196.79,300.25 C200.88,302.92 204.42,304.92 204.65,304.68 C205.52,303.82 188.13,289.54 178.13,282.92 C149.69,264.07 122.06,255.51 85.75,254.31 C72.88,253.89 66.67,253.31 65.98,252.47 C65.31,251.66 65.06,213.37 65.23,138.09 C65.47,38.78 65.68,24.81 67.00,23.98 C69.02,22.70 100.46,22.74 111.03,24.04 C121.91,25.38 139.17,29.45 150.00,33.24 C178.00,43.03 206.28,62.15 224.43,83.55 L229.77,89.84 L236.63,81.91 C261.60,53.07 298.68,32.40 337.99,25.41 C355.87,22.23 390.15,21.75 393.04,24.64 C393.66,25.26 393.92,67.19 393.75,139.55 L393.50,253.50 L375.88,254.18 C354.66,254.99 338.97,257.60 322.50,263.08 C299.25,270.80 275.69,284.43 261.24,298.53 L253.50,306.08 L262.24,300.54 C287.81,284.33 316.65,273.71 346.54,269.51 C355.94,268.18 363.99,267.89 383.29,268.16 L408.00,268.50 L408.00,164.75 L408.00,61.00 L419.50,61.00 L431.00,61.00 L431.04,125.25 C431.12,253.54 430.91,298.49 430.21,299.14 C429.82,299.50 424.52,298.76 418.42,297.49 C363.47,286.03 310.82,291.86 266.50,314.32 C254.57,320.37 241.49,328.65 235.22,334.13 C231.06,337.76 229.35,337.73 223.90,333.93 Z M234.00,313.23 C238.96,305.19 258.78,285.67 270.00,277.76 C300.28,256.43 337.75,244.00 371.75,244.00 L384.00,244.00 L384.00,138.35 L384.00,32.71 L367.25,33.29 C349.64,33.91 340.02,35.29 324.44,39.44 C291.54,48.20 260.81,67.79 240.94,92.68 L235.21,99.86 L234.59,113.18 C234.25,120.51 233.53,155.52 232.99,191.00 C231.79,269.20 230.92,301.00 229.97,301.00 C229.58,301.00 228.95,291.21 228.59,279.25 C227.94,258.36 225.02,117.34 225.00,106.00 C224.99,100.57 224.88,100.38 216.58,90.50 C194.00,63.64 160.69,44.23 125.00,37.14 C109.99,34.16 99.18,33.00 86.28,33.00 L75.00,33.00 L75.00,138.50 L75.00,244.00 L87.12,244.00 C115.76,244.00 144.65,251.68 170.74,266.23 C192.90,278.59 212.48,295.18 223.96,311.32 C226.97,315.54 229.67,318.98 229.96,318.95 C230.26,318.93 232.07,316.35 234.00,313.23 Z M313.17,194.75 C310.76,177.18 310.60,170.55 312.48,167.66 C314.73,164.23 315.59,164.31 317.55,168.10 C318.96,170.82 319.02,172.72 318.05,183.35 C316.69,198.26 315.96,203.00 315.02,203.00 C314.63,203.00 313.79,199.29 313.17,194.75 Z M281.50,155.33 C272.05,154.16 265.06,152.72 265.48,152.03 C266.61,150.21 297.29,147.82 299.78,149.37 C301.54,150.45 301.28,154.68 299.42,155.39 C297.78,156.02 286.77,155.98 281.50,155.33 Z M329.61,154.47 C327.69,152.55 328.57,150.11 331.61,148.96 C335.15,147.61 362.42,150.25 363.53,152.05 C364.08,152.94 361.51,153.57 351.50,154.98 C340.73,156.49 331.42,156.28 329.61,154.47 Z M312.40,136.48 C310.62,133.77 310.82,126.94 313.20,109.25 C315.01,95.75 315.99,98.19 318.04,121.29 C319.05,132.62 318.99,134.36 317.57,136.54 C315.53,139.65 314.46,139.64 312.40,136.48 Z" fill="currentColor" fill-rule="evenodd"/>
          </svg>
          DocSanctum
        </span>
        <div class="flex items-center gap-2">
          <button
            class="text-sm hover:text-blue-400"
            :title="t('app.openSearch', { shortcut: searchShortcutLabel })"
            @click="search.open()"
          >🔍</button>
          <button class="text-lg hover:text-blue-400" :title="t('app.addSource')" @click="showAdd = true">＋</button>
        </div>
      </div>
      <div class="overflow-y-auto flex-1 py-2 sidebar-scroll">
        <SourceList
          :selected-source-id="treeSourceId"
          @select-source="selectSource"
          @delete-source="requestDelete"
          @refresh-source="refreshSource"
          @edit-source="requestEdit"
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
          @click="toggleSettings"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          {{ t('app.settings') }}
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
      <ChangelogPage v-if="view === 'changelog'" class="flex-1 overflow-y-auto viewer-pane-scroll" @back="view = 'settings'" />
      <SettingsPanel v-else-if="view === 'settings'" class="flex-1 overflow-y-auto viewer-pane-scroll" @open-changelog="view = 'changelog'" />
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

    <CommandPalette />

    <AddSourceModal v-if="showAdd" @close="showAdd = false" />
    <EditSourceModal
      v-if="pendingEditSource"
      :source="pendingEditSource"
      @close="pendingEditId = null"
    />
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
import { useI18n } from 'vue-i18n'
import { onKeyStroke } from '@vueuse/core'
import SourceList from './components/Sidebar/SourceList.vue'
import FileTree from './components/Sidebar/FileTree.vue'
import AddSourceModal from './components/Sidebar/AddSourceModal.vue'
import EditSourceModal from './components/Sidebar/EditSourceModal.vue'
import ConfirmDeleteModal from './components/Sidebar/ConfirmDeleteModal.vue'
import SettingsPanel from './components/Settings/SettingsPanel.vue'
import ChangelogPage from './components/Settings/ChangelogPage.vue'
import ViewerPane from './components/Viewer/ViewerPane.vue'
import CommandPalette from './components/CommandPalette/CommandPalette.vue'
import { useSources } from './composables/useSources'
import { usePanes } from './composables/usePanes'
import { useTreeReveal } from './composables/useTreeReveal'
import { useSearch, searchShortcutLabel } from './composables/useSearch'

const { t } = useI18n()
const { sourcesQuery, remove } = useSources()
const { panes, activePaneId, openInActivePane, clearSource } = usePanes()
const { reveal } = useTreeReveal()
const search = useSearch()

const showAdd = ref(false)
const pendingDeleteId = ref<string | null>(null)
const pendingDeleteSource = computed(() =>
  sourcesQuery.data.value?.find((s) => s.id === pendingDeleteId.value) ?? null
)
const pendingEditId = ref<string | null>(null)
const pendingEditSource = computed(() =>
  sourcesQuery.data.value?.find((s) => s.id === pendingEditId.value) ?? null
)
const view = ref<'viewer' | 'settings' | 'changelog'>('viewer')

// Clicking the settings button again while already viewing settings (or its
// changelog subview) toggles back to the viewer instead of doing nothing.
function toggleSettings() {
  view.value = view.value === 'viewer' ? 'settings' : 'viewer'
}

// Esc closes the settings/changelog view and returns to the document viewer.
onKeyStroke('Escape', () => {
  if (view.value !== 'viewer') view.value = 'viewer'
})

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

function requestEdit(id: string) {
  pendingEditId.value = id
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
