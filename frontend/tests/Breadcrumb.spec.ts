import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
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

  it('renders nothing for an empty path', () => {
    const wrapper = mount(Breadcrumb, { props: { path: '' } })

    expect(wrapper.find('nav').exists()).toBe(false)
  })
})
