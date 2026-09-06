import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import Breadcrumb from '../src/components/Viewer/Breadcrumb.vue'

describe('Breadcrumb', () => {
  it('splits the file path into clickable segments and a current file label', () => {
    const wrapper = mount(Breadcrumb, {
      props: { path: 'guide/advanced/setup.md' },
    })

    const buttons = wrapper.findAll('.crumb-btn')
    expect(buttons.map((b) => b.text())).toEqual(['guide', 'advanced'])
    expect(wrapper.find('.crumb-current').text()).toBe('setup.md')
  })

  it('emits select-segment with the full path up to the clicked segment', async () => {
    const wrapper = mount(Breadcrumb, {
      props: { path: 'guide/advanced/setup.md' },
    })

    await wrapper.findAll('.crumb-btn')[1].trigger('click')

    expect(wrapper.emitted('select-segment')?.[0]).toEqual(['guide/advanced'])
  })

  it('abbreviates long paths with an ellipsis', () => {
    const wrapper = mount(Breadcrumb, {
      props: { path: 'a/b/c/d/e/file.md' },
    })

    expect(wrapper.find('.crumb-ellipsis').exists()).toBe(true)
  })

  it('copies the source root joined with the document path', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    Object.defineProperty(navigator, 'permissions', {
      value: {
        query: vi.fn().mockResolvedValue({
          state: 'granted',
          addEventListener: () => {},
          removeEventListener: () => {},
        }),
      },
      configurable: true,
    })

    const wrapper = mount(Breadcrumb, {
      props: { path: 'guide/setup.md', sourceRoot: '/home/me/docs/' },
    })
    await flushPromises()
    await wrapper.find('.crumb-copy-btn').trigger('click')

    expect(writeText).toHaveBeenCalledWith('/home/me/docs/guide/setup.md')
  })

  it('shell-quotes a copied path that contains a space', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })

    const wrapper = mount(Breadcrumb, {
      props: { path: 'Game/code + cline.md', sourceRoot: '/home/me/docs' },
    })
    await flushPromises()
    await wrapper.find('.crumb-copy-btn').trigger('click')

    expect(writeText).toHaveBeenCalledWith('"/home/me/docs/Game/code + cline.md"')
  })

  it('renders nothing for an empty path', () => {
    const wrapper = mount(Breadcrumb, { props: { path: '' } })

    expect(wrapper.find('nav').exists()).toBe(false)
  })
})
