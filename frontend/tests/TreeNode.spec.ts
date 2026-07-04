import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import TreeNode from '../src/components/Sidebar/TreeNode.vue'
import { usePanes } from '../src/composables/usePanes'

function resetPanes() {
  const { panes, closePane, setPaneDocument } = usePanes()
  if (panes.value.length > 1) closePane(panes.value[1].id)
  setPaneDocument(1, null, null)
}

const leafNode = { path: 'a.md', name: 'a.md', is_dir: false }

describe('TreeNode pane color indicators', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/')
    resetPanes()
  })

  it('renders no indicator when the file is not open in any pane', () => {
    const wrapper = mount(TreeNode, { props: { node: leafNode, sourceId: 'src-1' } })
    expect(wrapper.findAll('.pane-match-dot')).toHaveLength(0)
  })

  it('renders one indicator with the pane color when open in a single pane', () => {
    const { openInActivePane } = usePanes()
    openInActivePane('src-1', 'a.md')

    const wrapper = mount(TreeNode, { props: { node: leafNode, sourceId: 'src-1' } })
    const dots = wrapper.findAll('.pane-match-dot')
    expect(dots).toHaveLength(1)
    expect(dots[0].classes()).toContain('bg-blue-500')
  })

  it('renders two indicators when the same file is open in both panes', () => {
    const { openInActivePane, addPane, setActivePane } = usePanes()
    openInActivePane('src-1', 'a.md')
    addPane()
    setActivePane(2)
    openInActivePane('src-1', 'a.md')

    const wrapper = mount(TreeNode, { props: { node: leafNode, sourceId: 'src-1' } })
    const dots = wrapper.findAll('.pane-match-dot')
    expect(dots).toHaveLength(2)
    expect(dots[0].classes()).toContain('bg-blue-500')
    expect(dots[1].classes()).toContain('bg-amber-500')
  })

  it('does not show an indicator for a different file path', () => {
    const { openInActivePane } = usePanes()
    openInActivePane('src-1', 'a.md')

    const wrapper = mount(TreeNode, { props: { node: { ...leafNode, path: 'b.md' }, sourceId: 'src-1' } })
    expect(wrapper.findAll('.pane-match-dot')).toHaveLength(0)
  })
})
