<template>
  <div class="reading-progress-track" role="progressbar" :aria-valuenow="Math.round(ratio * 100)" aria-valuemin="0" aria-valuemax="100">
    <div class="reading-progress-fill" :style="{ width: `${ratio * 100}%` }" />
  </div>
  <Transition name="fade">
    <button
      v-if="showBackToTop"
      type="button"
      class="back-to-top"
      aria-label="맨 위로 이동"
      @click="scrollToTop"
    >↑</button>
  </Transition>
</template>

<script setup lang="ts">
import { toValue, type MaybeRefOrGetter } from 'vue'
import { useReadingProgress } from '../../composables/useReadingProgress'

const props = defineProps<{ container: MaybeRefOrGetter<HTMLElement | null | undefined> }>()
const { ratio, showBackToTop, scrollToTop } = useReadingProgress(() => toValue(props.container))
</script>

<style scoped>
.reading-progress-track {
  position: sticky;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: transparent;
  z-index: 20;
}
.reading-progress-fill {
  height: 100%;
  background: #3b82f6;
  transition: width 0.1s linear;
}
.back-to-top {
  position: fixed;
  right: 1.5rem;
  bottom: 1.5rem;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 9999px;
  border: none;
  background: #3b82f6;
  color: white;
  font-size: 1.1rem;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
  z-index: 20;
}
.back-to-top:hover,
.back-to-top:focus-visible {
  background: #2563eb;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
