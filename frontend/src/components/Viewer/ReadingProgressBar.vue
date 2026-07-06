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
 * height:0 so this never adds to the scroll container's scrollHeight — a
 * non-zero height here always overflowed the container by that many pixels
 * (even for documents shorter than the pane), forcing a permanent scrollbar
 * to appear regardless of content length. The visible 3px bar is drawn by
 * .reading-progress-fill, absolutely positioned within this sticky wrapper.
 */
.reading-progress-track {
  position: sticky;
  top: 0;
  left: 0;
  right: 0;
  height: 0;
  z-index: 20;
}
.reading-progress-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 3px;
  transition: width 0.1s linear;
}
/*
 * Each pane has its own independent scroll container (multi-pane support),
 * so this button sticks to the bottom of its own scroll container instead
 * of being viewport-fixed — that way it never overlaps or gets ambiguous
 * about which pane it belongs to when two panes are open. The height:0
 * wrapper keeps it from affecting scroll height, and flex right-aligns it.
 */
.back-to-top-anchor {
  position: sticky;
  bottom: 1.5rem;
  height: 0;
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
