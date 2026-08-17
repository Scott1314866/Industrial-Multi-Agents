import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import AppShell from '@/components/AppShell.vue'

const Page = defineComponent({ template: '<div>page</div>' })

describe('AppShell navigation', () => {
  it('navigates from the engineer dashboard to each workspace', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/engineer', component: Page },
        { path: '/engineer/diagnosis', component: Page },
        { path: '/engineer/audit', component: Page },
        { path: '/engineer/safety', component: Page },
      ],
    })
    const pinia = createPinia()
    await router.push('/engineer')
    await router.isReady()
    const wrapper = mount(AppShell, {
      props: { mode: 'engineer' },
      global: { plugins: [pinia, router] },
    })

    const links = wrapper.findAll('nav a')
    expect(links.map((link) => link.attributes('href'))).toEqual([
      '/engineer',
      '/engineer/diagnosis',
      '/engineer/audit',
      '/engineer/safety',
    ])

    await links[1].trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/engineer/diagnosis')
  })
})
