<template>
  <div class="flex h-screen bg-gray-900 text-white overflow-hidden">
    <!-- Sidebar -->
    <aside class="w-64 flex flex-col border-r border-gray-700 shrink-0">
      <div class="flex items-center justify-between px-3 py-3 border-b border-gray-700">
        <span class="font-semibold text-sm">DocSanctum</span>
        <button class="text-lg hover:text-blue-400" title="소스 추가" @click="showAdd = true">＋</button>
      </div>
      <div class="overflow-y-auto flex-1 py-2">
        <SourceList
          :selected-source-id="selectedSourceId"
          @select-source="selectSource"
          @delete-source="deleteSource"
          @refresh-source="refreshSource"
        />
        <div v-if="selectedSourceId" class="border-t border-gray-700 mt-2 pt-2">
          <FileTree
            :source-id="selectedSourceId"
            :selected-path="selectedFile?.path ?? null"
            @select-file="selectFile"
          />
        </div>
      </div>
    </aside>

    <!-- Viewer -->
    <main class="flex-1 overflow-y-auto">
      <MarkdownViewer
        v-if="selectedFile"
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
import { ref } from 'vue'
import SourceList from './components/Sidebar/SourceList.vue'
import FileTree from './components/Sidebar/FileTree.vue'
import AddSourceModal from './components/Sidebar/AddSourceModal.vue'
import MarkdownViewer from './components/Viewer/MarkdownViewer.vue'
import EmptyState from './components/Viewer/EmptyState.vue'
import { useSources } from './composables/useSources'

const { remove, sourcesQuery } = useSources()

const showAdd = ref(false)
const selectedSourceId = ref<string | null>(null)
const selectedFile = ref<{ sourceId: string; path: string } | null>(null)

function selectSource(id: string) {
  selectedSourceId.value = id
  selectedFile.value = null
}

function selectFile(sourceId: string, path: string) {
  selectedFile.value = { sourceId, path }
}

function navigateFile(path: string) {
  if (selectedFile.value) {
    const dir = selectedFile.value.path.split('/').slice(0, -1).join('/')
    const resolved = dir ? `${dir}/${path}` : path
    selectedFile.value = { sourceId: selectedFile.value.sourceId, path: resolved }
  }
}

async function deleteSource(id: string) {
  await remove.mutateAsync(id)
  if (selectedSourceId.value === id) {
    selectedSourceId.value = null
    selectedFile.value = null
  }
}

async function refreshSource(id: string) {
  const { api } = await import('./services/api')
  await api.refreshSource(id)
}
</script>
