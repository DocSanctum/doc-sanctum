<template>
  <div class="reading-progress-track" role="progressbar" :aria-valuenow="Math.round(ratio * 100)" aria-valuemin="0" aria-valuemax="100">
    <div class="reading-progress-fill" :style="{ width: `${ratio * 100}%` }" />
  </div>
  <div class="back-to-top-anchor">
    <Transition name="fade">
      <button
        v-if="showBackToTop"
        type="button"
        class="back-to-top"
        aria-label="맨 위로 이동"
        @click="scrollToTop"
      >↑</button>
    </Transition>
  </div>
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
/*
 * 패널마다 독립된 스크롤 컨테이너를 가지므로(멀티 패널 지원), 이 버튼은
 * 뷰포트 기준 fixed 대신 자신이 속한 스크롤 컨테이너 하단에 sticky로
 * 고정한다 — 패널이 2개 열려도 버튼이 겹치거나 어느 패널 것인지 모호해지지
 * 않는다. height:0 래퍼로 스크롤 높이에 영향을 주지 않게 하고, flex로
 * 우측 정렬한다.
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
  background: #3b82f6;
  color: white;
  font-size: 1.1rem;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
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
