<template>
  <Teleport to="body">
    <div
      ref="dialogRef"
      class="zoom-lightbox"
      role="dialog"
      aria-modal="true"
      tabindex="-1"
      data-testid="zoom-lightbox"
      @click.self="emit('close')"
    >
      <div
        ref="viewportRef"
        class="zoom-viewport"
        :class="{ 'zoom-viewport--dragging': dragging }"
        @wheel="onWheel"
        @pointerdown="startDrag"
        @pointermove="onPointerMove"
        @pointerup="endDrag"
        @pointercancel="endDrag"
        @dblclick="fit"
      >
        <div class="zoom-content" :style="style">
          <!-- The SVG is mermaid output already sanitized by the caller. -->
          <div v-if="svg" ref="svgHostRef" class="zoom-svg" v-html="svg" />
          <img v-else-if="imageSrc" :src="imageSrc" :alt="alt" draggable="false" @load="onImageLoad" />
        </div>
      </div>
      <div class="zoom-toolbar" @click.stop>
        <button type="button" :title="t('viewer.zoom.zoomOut')" :aria-label="t('viewer.zoom.zoomOut')" @click="zoomBy(1 / STEP)">−</button>
        <span class="zoom-percent" aria-live="polite">{{ percent }}%</span>
        <button type="button" :title="t('viewer.zoom.zoomIn')" :aria-label="t('viewer.zoom.zoomIn')" @click="zoomBy(STEP)">+</button>
        <button type="button" :title="t('viewer.zoom.fit')" @click="fit">{{ t('viewer.zoom.fit') }}</button>
        <button type="button" class="zoom-close" :title="t('viewer.markdown.exitFullscreen')" :aria-label="t('viewer.markdown.exitFullscreen')" @click="emit('close')">✕</button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { onKeyStroke } from '@vueuse/core'
import { usePanZoom } from '../../composables/usePanZoom'

const props = defineProps<{ svg?: string; imageSrc?: string; alt?: string }>()
const emit = defineEmits<{ close: [] }>()
const { t } = useI18n()

const STEP = 1.25
const dialogRef = ref<HTMLElement | null>(null)
const viewportRef = ref<HTMLElement | null>(null)
const svgHostRef = ref<HTMLElement | null>(null)
const dragging = ref(false)

// Vector diagrams may be enlarged to fill the screen; raster images are
// capped at their natural size so they are never blurry when first shown.
const maxFit = computed(() => (props.svg ? 2 : 1))
const { style, percent, setContentSize, fit, zoomBy, onWheel, onPointerDown, onPointerMove, onPointerUp } =
  usePanZoom(viewportRef, maxFit)

function startDrag(e: PointerEvent) {
  dragging.value = true
  onPointerDown(e)
}

function endDrag(e: PointerEvent) {
  onPointerUp(e)
  dragging.value = false
}

function onImageLoad(e: Event) {
  const img = e.target as HTMLImageElement
  setContentSize({ width: img.naturalWidth, height: img.naturalHeight })
}

function measureSvg() {
  const svg = svgHostRef.value?.querySelector('svg')
  if (!svg) return
  const viewBox = svg.getAttribute('viewBox')?.split(/\s+/).map(Number)
  const width = Number(svg.getAttribute('width')) || viewBox?.[2] || 0
  const height = Number(svg.getAttribute('height')) || viewBox?.[3] || 0
  setContentSize({ width, height })
}

onMounted(async () => {
  dialogRef.value?.focus()
  await nextTick()
  if (props.svg) measureSvg()
})

onKeyStroke('Escape', () => emit('close'))
onKeyStroke(['+', '='], () => zoomBy(STEP))
onKeyStroke('-', () => zoomBy(1 / STEP))
onKeyStroke('0', () => fit())
</script>

<style>
.zoom-lightbox {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  background: rgba(0, 0, 0, 0.6);
  outline: none;
}
.zoom-viewport {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border-radius: 8px;
  cursor: grab;
  touch-action: none;
  user-select: none;
}
.zoom-viewport--dragging { cursor: grabbing; }
:root.dark .zoom-viewport { background: #161b22; }
:root:not(.dark) .zoom-viewport { background: #f9fafb; }
.zoom-content {
  position: absolute;
  top: 0;
  left: 0;
  transform-origin: 0 0;
  will-change: transform;
}
.zoom-content img,
.zoom-svg svg {
  display: block;
  max-width: none;
  pointer-events: none;
}
.zoom-toolbar {
  position: absolute;
  bottom: 2.75rem;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.3rem;
  border-radius: 9999px;
  background: rgba(17, 24, 39, 0.85);
  color: #e5e7eb;
  font-size: 0.8rem;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}
.zoom-toolbar button {
  min-width: 2rem;
  height: 2rem;
  padding: 0 0.6rem;
  border-radius: 9999px;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.zoom-toolbar button:hover,
.zoom-toolbar button:focus-visible { background: rgba(255, 255, 255, 0.15); }
.zoom-toolbar .zoom-close:hover { color: #f87171; }
.zoom-percent {
  min-width: 3.5rem;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
</style>
