<template>
  <div class="reading-progress-track" role="progressbar" :aria-valuenow="Math.round(ratio * 100)" aria-valuemin="0" aria-valuemax="100">
    <div class="reading-progress-fill" :class="paneColorClass(props.color, 'bg')" :style="{ width: `${ratio * 100}%` }" />
  </div>
  <div class="back-to-top-anchor">
    <Transition name="fade">
      <button
        v-if="showBackToTop"
        type="button"
        class="back-to-top"
        :class="[paneColorClass(props.color, 'bg'), paneColorClass(props.color, 'solidHover')]"
        aria-label="맨 위로 이동"
        @click="scrollToTop"
      >↑</button>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { toValue, type MaybeRefOrGetter } from 'vue'
import { useReadingProgress } from '../../composables/useReadingProgress'
import { paneColorClass } from '../../composables/usePanes'
import type { PaneColor } from '../../types'

const props = defineProps<{ container: MaybeRefOrGetter<HTMLElement | null | undefined>; color: PaneColor }>()
const { ratio, showBackToTop, scrollToTop } = useReadingProgress(() => toValue(props.container))
</script>

<style scoped>
/*
 * This renders as a sibling of the pane's scroll container (see
 * ViewerPane.vue), not inside it, and is positioned absolutely against the
 * pane's own `position: relative` root instead of `position: sticky` inside
 * the scrollable element. Two reasons: a sticky child previously added to
 * the container's scrollHeight, forcing a scrollbar even on documents
 * shorter than the pane; and WebKit/Safari has long-standing bugs computing
 * the scrollable max of a container that has a `position: sticky`
 * descendant, which kept the reading-progress ratio from ever reaching 100%
 * there. Living outside the scroll container sidesteps both.
 */
.reading-progress-track {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  pointer-events: none;
  z-index: 20;
}
.reading-progress-fill {
  height: 100%;
  transition: width 0.1s linear;
}
.back-to-top-anchor {
  position: absolute;
  bottom: 1.5rem;
  left: 0;
  right: 0;
  display: flex;
  justify-content: flex-end;
  padding-right: 1.5rem;
  pointer-events: none;
  z-index: 20;
}
.back-to-top {
  pointer-events: auto;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 9999px;
  border: none;
  color: white;
  font-size: 1.1rem;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
  transition: background-color 0.15s ease;
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
