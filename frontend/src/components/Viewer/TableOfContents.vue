<template>
  <nav v-if="entries.length > 0" class="toc" aria-label="목차">
    <p class="toc-title">목차</p>
    <ul>
      <li
        v-for="entry in entries"
        :key="entry.id"
        :style="{ paddingLeft: `${(entry.level - minLevel) * 0.75}rem` }"
      >
        <a
          href="#"
          class="toc-link"
          :class="{ active: entry.id === activeId }"
          @click.prevent="$emit('select', entry.id)"
        >{{ entry.text }}</a>
      </li>
    </ul>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TocEntry } from '../../composables/useToc'

const props = defineProps<{ entries: TocEntry[]; activeId: string | null }>()
defineEmits<{ select: [id: string] }>()

const minLevel = computed(() =>
  props.entries.length ? Math.min(...props.entries.map((e) => e.level)) : 1
)
</script>

<style scoped>
.toc {
  position: sticky;
  top: 2rem;
  max-height: calc(100vh - 4rem);
  overflow-y: auto;
  font-size: 0.8rem;
  padding-left: 1rem;
  border-left: 1px solid rgba(148, 163, 184, 0.3);
}
.toc-title {
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.7rem;
  color: #9ca3af;
  margin: 0 0 0.5rem;
}
.toc ul {
  list-style: none;
  margin: 0;
  padding: 0;
}
.toc li {
  margin: 0.15rem 0;
}
.toc-link {
  display: block;
  color: #6b7280;
  text-decoration: none;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.toc-link:hover,
.toc-link:focus-visible {
  color: #3b82f6;
}
.toc-link.active {
  color: #3b82f6;
  font-weight: 600;
}
</style>
