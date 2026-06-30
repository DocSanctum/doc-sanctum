<template>
  <div class="fixed inset-0 bg-black/60 flex items-end justify-start z-50" @click.self="$emit('close')">
    <div class="bg-gray-800 border border-gray-700 rounded-tr-xl w-72 p-5 mb-12 ml-2 shadow-2xl">
      <div class="flex items-center justify-between mb-4">
        <span class="font-semibold text-sm">설정</span>
        <button class="text-gray-400 hover:text-white text-lg leading-none" @click="$emit('close')">✕</button>
      </div>

      <div class="space-y-4 text-sm">
        <div>
          <label class="text-gray-400 text-xs uppercase tracking-wider block mb-2">뷰어 폰트 크기</label>
          <div class="flex gap-2">
            <button
              v-for="size in fontSizes"
              :key="size.value"
              class="flex-1 py-1.5 rounded text-xs border"
              :class="currentFontSize === size.value
                ? 'bg-blue-600 border-blue-500 text-white'
                : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'"
              @click="setFontSize(size.value)"
            >
              {{ size.label }}
            </button>
          </div>
        </div>

        <div>
          <label class="text-gray-400 text-xs uppercase tracking-wider block mb-2">코드 테마</label>
          <select
            v-model="currentTheme"
            class="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-gray-200 text-xs outline-none focus:border-blue-500"
            @change="onThemeChange"
          >
            <option v-for="t in THEME_OPTIONS" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </div>

        <div class="pt-2 border-t border-gray-700 text-gray-500 text-xs">
          DocSanctum v0.1.0
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { applyCodeTheme, THEME_OPTIONS } from '../../composables/useCodeTheme'
import { useViewerSettings } from '../../composables/useViewerSettings'

defineEmits<{ close: [] }>()

const fontSizes = [
  { label: '소', value: 'sm' },
  { label: '중', value: 'base' },
  { label: '대', value: 'lg' },
]

const { fontSize: currentFontSize, setFontSize } = useViewerSettings()
const currentTheme = ref(localStorage.getItem('ds-code-theme') ?? 'github-dark')

function onThemeChange() {
  applyCodeTheme(currentTheme.value)
}
</script>
