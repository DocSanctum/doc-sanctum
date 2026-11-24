import { describe, it, expect } from 'vitest'
import { computed } from 'vue'
import { mount } from '@vue/test-utils'
import TreeNode from '../src/components/Sidebar/TreeNode.vue'
import { INDEX_ERRORS, countErrorsUnder } from '../src/composables/useIndexErrors'
import type { IndexError } from '../src/types'

function errors(...paths: string[]): Map<string, IndexError> {
  return new Map(
    paths.map((path) => [
      path,
      { path, kind: 'no_text', message: 'No extractable text', updated_at: '2026-11-24' },
    ]),
  )
}

const tree = {
  path: '',
  name: 'root',
  is_dir: true,
  children: [
    {
      path: 'docs',
      name: 'docs',
      is_dir: true,
      children: [{ path: 'docs/scan.pdf', name: 'scan.pdf', is_dir: false }],
    },
    { path: 'ok.md', name: 'ok.md', is_dir: false },
  ],
}

function mountTree(map: Map<string, IndexError>) {
  return mount(TreeNode, {
    props: { node: tree, sourceId: 'src-1' },
    global: { provide: { [INDEX_ERRORS as symbol]: computed(() => map) } },
  })
}

describe('countErrorsUnder', () => {
  it('counts only documents inside the folder', () => {
    const map = errors('docs/a.pdf', 'docs/sub/b.pdf', 'docsx/c.pdf')
    expect(countErrorsUnder(map, 'docs')).toBe(2)
    expect(countErrorsUnder(map, '')).toBe(3)
  })
})

describe('TreeNode index error badges', () => {
  it('marks only the failed file and explains why in the tooltip', () => {
    const wrapper = mountTree(errors('docs/scan.pdf'))
    const badges = wrapper.findAll('.index-error-badge')
    expect(badges).toHaveLength(1)
    expect(badges[0].attributes('title')).toContain('No extractable text')
  })

  it('shows no badges when nothing failed', () => {
    expect(mountTree(errors()).findAll('.index-error-badge')).toHaveLength(0)
  })

  it('flags a collapsed folder that hides a failed file', async () => {
    const wrapper = mountTree(errors('docs/scan.pdf'))
    const docsFolder = wrapper.findAll('button').find((b) => b.text().startsWith('▾docs'))!
    await docsFolder.trigger('click')
    const badges = wrapper.findAll('.index-error-badge')
    expect(badges).toHaveLength(1)
    expect(badges[0].attributes('title')).toContain('1')
  })
})
