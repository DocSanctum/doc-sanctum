import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import SourceList from '../src/components/Sidebar/SourceList.vue'
import { en } from '../src/i18n/locales/en'
import { indexProgress, isIndexing } from '../src/utils/indexProgress'
import type { Source } from '../src/types'

function source(overrides: Partial<Source> = {}): Source {
  return {
    id: 's1',
    name: 'Docs',
    type: 'github',
    path: 'org/repo',
    polling_interval_seconds: 300,
    created_at: '2026-01-01',
    status: 'active',
    error_message: null,
    icon: null,
    access_token_configured: false,
    index_reason: null,
    index_done: null,
    index_total: null,
    ...overrides,
  }
}

describe('indexProgress', () => {
  it('is null for an idle source', () => {
    expect(isIndexing(source())).toBe(false)
    expect(indexProgress(source())).toBeNull()
  })

  it('counts a background re-index even while the status stays active', () => {
    const progress = indexProgress(
      source({ index_reason: 'model', index_done: 1240, index_total: 3000 }),
    )
    expect(progress).toEqual({ reasonKey: 'model', done: 1240, total: 3000, percent: 41 })
  })

  it('falls back to "changes" with no reason and to no count before listing', () => {
    expect(indexProgress(source({ status: 'syncing' }))).toEqual({
      reasonKey: 'changes',
      done: null,
      total: null,
      percent: null,
    })
  })

  it('never reports more than the total', () => {
    expect(indexProgress(source({ index_done: 12, index_total: 10 }))?.percent).toBe(100)
  })
})

async function mountList(sources: Source[]) {
  const queryClient = new QueryClient()
  queryClient.setQueryData(['sources'], sources)
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en } })
  const wrapper = mount(SourceList, {
    props: { selectedSourceId: null },
    global: { plugins: [i18n, [VueQueryPlugin, { queryClient }]] },
  })
  await wrapper.vm.$nextTick()
  return wrapper
}

describe('SourceList indexing line', () => {
  it('shows the reason, counts and a bar instead of the path while indexing', async () => {
    const wrapper = await mountList([
      source({ index_reason: 'model', index_done: 1240, index_total: 3000 }),
    ])
    const line = wrapper.find('.index-progress-text')
    expect(line.find('.index-progress-count').text()).toBe('1,240/3,000')
    expect(line.attributes('title')).toBe('Model changed · 1,240/3,000')
    expect(wrapper.find('.index-progress-bar').attributes('style')).toContain('width: 41%')
    expect(wrapper.text()).not.toContain('org/repo')
  })

  it('shows the path when the source is idle', async () => {
    const wrapper = await mountList([source()])
    expect(wrapper.find('.index-progress-text').exists()).toBe(false)
    expect(wrapper.text()).toContain('org/repo')
  })
})
