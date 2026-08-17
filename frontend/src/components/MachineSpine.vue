<script setup lang="ts">
import { computed } from 'vue'
import { Check, CircleDashed, Database, ShieldAlert } from 'lucide-vue-next'
import type { RunEvent } from '@/types'

const props = defineProps<{ events: RunEvent[]; active: boolean }>()
const nodes = computed(() => {
  const completed = new Set(props.events.filter((event) => event.type === 'agent.completed').map((event) => event.node))
  return [
    { id: 'context', label: '设备上下文', done: props.events.some((event) => event.type === 'run.started'), icon: Database },
    { id: 'fault_diagnosis', label: '故障诊断', done: completed.has('fault_diagnosis'), icon: CircleDashed },
    { id: 'quality_analysis', label: '质量分析', done: completed.has('quality_analysis'), icon: CircleDashed },
    { id: 'safety', label: '安全门控', done: props.events.some((event) => event.type === 'run.completed'), icon: ShieldAlert },
  ]
})
</script>

<template>
  <div class="machine-spine" :class="{ 'is-live': active }">
    <div class="spine-head"><span>分析流程</span><b>{{ active ? '执行中' : '待命' }}</b></div>
    <div v-for="(node, index) in nodes" :key="node.id" class="spine-node" :class="{ done: node.done }">
      <span class="spine-index">0{{ index + 1 }}</span>
      <span class="spine-dot"><Check v-if="node.done" :size="11" /><component :is="node.icon" v-else :size="12" /></span>
      <span class="spine-label">{{ node.label }}</span>
    </div>
  </div>
</template>
