<template>
  <div
    class="flex h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white overflow-hidden"
    @mousemove="onDrag"
    @mouseup="stopDrag"
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
          :selected-source-id="selectedSourceId"
          @select-source="selectSource"
          @delete-source="deleteSource"
          @refresh-source="refreshSource"
        />
        <div v-if="selectedSourceId" class="border-t border-gray-200 dark:border-gray-700 mt-2 pt-2">
          <FileTree
            :source-id="selectedSourceId"
            :selected-path="selectedFile?.path ?? null"
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
    <main ref="mainRef" class="flex-1 overflow-y-auto" :class="{ 'select-none': dragging }">
      <ReadingProgressBar v-if="view === 'viewer' && selectedFile" :container="getMainEl" />
      <ChangelogPage v-if="view === 'changelog'" @back="view = 'settings'" />
      <SettingsPanel v-else-if="view === 'settings'" @open-changelog="view = 'changelog'" />
      <MarkdownViewer
        v-else-if="selectedFile"
        :source-id="selectedFile.sourceId"
        :file-path="selectedFile.path"
        @navigate="navigateFile"
      />
      <EmptyState v-else />
    </main>

    <AddSourceModal v-if="showAdd" @close="showAdd = false" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import SourceList from './components/Sidebar/SourceList.vue'
import FileTree from './components/Sidebar/FileTree.vue'
import AddSourceModal from './components/Sidebar/AddSourceModal.vue'
import SettingsPanel from './components/Settings/SettingsPanel.vue'
import ChangelogPage from './components/Settings/ChangelogPage.vue'
import MarkdownViewer from './components/Viewer/MarkdownViewer.vue'
import EmptyState from './components/Viewer/EmptyState.vue'
import ReadingProgressBar from './components/Viewer/ReadingProgressBar.vue'
import { useSources } from './composables/useSources'
import { useViewerUrl } from './composables/useViewerUrl'

const { remove } = useSources()
const viewerUrl = useViewerUrl()

const showAdd = ref(false)
const view = ref<'viewer' | 'settings' | 'changelog'>('viewer')

// 최초 로드 시 URL의 source/file 쿼리 파라미터를 그대로 신뢰해 복원한다(FR-006).
// 존재하지 않는 source/file이면 하위 컴포넌트의 기존 에러 처리(fetchError 등)가
// 자연스럽게 "찾을 수 없음" 상태를 보여준다(FR-014, Clarifications Q2) — 별도
// 사전 검증 로직을 추가하지 않는다.
const initialSourceId = viewerUrl.getSourceId()
const initialFilePath = viewerUrl.getFilePath()
const selectedSourceId = ref<string | null>(initialSourceId)
const selectedFile = ref<{ sourceId: string; path: string } | null>(
  initialSourceId && initialFilePath ? { sourceId: initialSourceId, path: initialFilePath } : null
)

const mainRef = ref<HTMLElement | null>(null)
function getMainEl() {
  return mainRef.value
}

// 문서 전환 시 읽기 진행률/맨 위로 버튼 상태가 이전 문서의 스크롤 위치를
// 그대로 물려받지 않도록 스크롤 컨테이너를 초기화한다(FR-011).
watch(
  () => selectedFile.value,
  () => {
    mainRef.value?.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior })
  }
)

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

function setSelectedFile(sourceId: string, path: string) {
  selectedFile.value = { sourceId, path }
  view.value = 'viewer'
  viewerUrl.setLocation(sourceId, path)
  viewerUrl.setHeadingId(null)
}

function selectSource(id: string) {
  selectedSourceId.value = id
  selectedFile.value = null
  viewerUrl.setLocation(id, null)
  viewerUrl.setHeadingId(null)
}

function selectFile(sourceId: string, path: string) {
  setSelectedFile(sourceId, path)
}

function navigateFile(path: string) {
  if (selectedFile.value) {
    const dir = selectedFile.value.path.split('/').slice(0, -1).join('/')
    const resolved = dir ? `${dir}/${path}` : path
    setSelectedFile(selectedFile.value.sourceId, resolved)
  }
}

async function deleteSource(id: string) {
  await remove.mutateAsync(id)
  if (selectedSourceId.value === id) {
    selectedSourceId.value = null
    selectedFile.value = null
    viewerUrl.setLocation(null, null)
    viewerUrl.setHeadingId(null)
  }
}

async function refreshSource(id: string) {
  const { api } = await import('./services/api')
  await api.refreshSource(id)
}
</script>
