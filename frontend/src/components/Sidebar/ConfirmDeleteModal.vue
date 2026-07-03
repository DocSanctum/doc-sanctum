<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="$emit('cancel')">
    <div class="bg-white dark:bg-gray-800 rounded-lg p-6 w-96 shadow-xl">
      <h2 class="text-gray-900 dark:text-white font-semibold mb-2">소스 삭제</h2>
      <p class="text-sm text-gray-600 dark:text-gray-300 mb-4">
        <span class="font-medium">{{ sourceName }}</span>을(를) 정말 삭제하시겠습니까?
        인덱싱된 데이터가 함께 제거되며 되돌릴 수 없습니다.
      </p>
      <div class="flex gap-2 justify-end">
        <button type="button" class="btn-secondary" @click="$emit('cancel')">취소</button>
        <button type="button" class="btn-primary bg-red-600 hover:bg-red-700" :disabled="loading" @click="$emit('confirm')">
          {{ loading ? '삭제 중...' : '삭제' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ sourceName: string; loading: boolean }>()
defineEmits<{ confirm: []; cancel: [] }>()
</script>
