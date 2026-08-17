import { mount } from '@vue/test-utils'
import MachineSpine from '../MachineSpine.vue'

describe('MachineSpine', () => {
  it('marks a completed agent node', () => {
    const wrapper = mount(MachineSpine, {
      props: {
        active: true,
        events: [{
          id: '1', run_id: 'run', type: 'agent.completed', timestamp: new Date().toISOString(),
          node: 'fault_diagnosis', message: 'done', data: {},
        }],
      },
    })
    expect(wrapper.text()).toContain('故障诊断')
    expect(wrapper.findAll('.spine-node.done')).toHaveLength(1)
  })
})

