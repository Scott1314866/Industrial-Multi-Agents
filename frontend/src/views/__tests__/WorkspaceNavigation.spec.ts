import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DiagnosisWorkspace from '@/views/DiagnosisWorkspace.vue'
import EngineerWorkspace from '@/views/EngineerWorkspace.vue'

const machines = [
  { id: 'IMM-240A', name: 'IMM-240A · MX-240', status: 'running' as const },
  { id: 'IMM-320B', name: 'IMM-320B · MX-320', status: 'warning' as const },
  { id: 'IMM-450C', name: 'IMM-450C · MX-450', status: 'maintenance' as const },
]
const context = {
  machine_id: 'IMM-320B', model: 'MX-320', status: 'warning' as const,
  alarm_codes: ['H-08'], mold_cycles: 1200, active_batch: 'B-01',
  telemetry: [{
    timestamp: '2026-08-17T10:00:00Z', oil_temperature_c: 51,
    injection_pressure_mpa: 93, injection_speed_mm_s: 42,
    cycle_time_s: 21, servo_load_pct: 63, quality_score: 97,
  }],
}

const apiMock = vi.hoisted(() => ({
  machines: vi.fn(), telemetry: vi.fn(), ragStatus: vi.fn(),
}))

vi.mock('@/lib/api', () => ({ api: apiMock }))

const ShellStub = defineComponent({ template: '<div><slot /></div>' })
const ConsoleStub = defineComponent({
  props: ['machineId'],
  template: '<div data-test="analysis-console" :data-machine="machineId" />',
})

function routerFor(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/engineer', component: EngineerWorkspace },
      { path: '/engineer/diagnosis', component: DiagnosisWorkspace, props: { mode: 'engineer' } },
    ],
  })
  return router.push(path).then(() => router)
}

beforeEach(() => {
  apiMock.machines.mockResolvedValue(machines)
  apiMock.telemetry.mockImplementation((id: string) => Promise.resolve({ ...context, machine_id: id }))
  apiMock.ragStatus.mockResolvedValue({ status: 'available', mode: 'fake' })
})

describe('workspace responsibilities', () => {
  it('keeps the dashboard free of the diagnosis console and links the selected machine', async () => {
    const router = await routerFor('/engineer')
    const wrapper = mount(EngineerWorkspace, {
      global: { plugins: [createPinia(), router], stubs: { AppShell: ShellStub, TelemetryChart: true } },
    })
    await flushPromises()

    expect(wrapper.find('[data-test="analysis-console"]').exists()).toBe(false)
    expect(wrapper.get('.diagnosis-link').attributes('href')).toBe('/engineer/diagnosis?machine=IMM-320B')
  })

  it.each([
    ['/engineer/diagnosis?machine=IMM-450C', 'IMM-450C'],
    ['/engineer/diagnosis', 'IMM-320B'],
    ['/engineer/diagnosis?machine=UNKNOWN', 'IMM-320B'],
  ])('selects a safe machine for %s', async (path, expected) => {
    const router = await routerFor(path)
    const wrapper = mount(DiagnosisWorkspace, {
      props: { mode: 'engineer' },
      global: {
        plugins: [router],
        stubs: { AppShell: ShellStub, AnalysisConsole: ConsoleStub },
      },
    })
    await flushPromises()

    expect(wrapper.get('[data-test="analysis-console"]').attributes('data-machine')).toBe(expected)
    expect(router.currentRoute.value.query.machine).toBe(expected)
  })
})
