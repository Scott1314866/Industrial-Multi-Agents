<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Activity, ArrowRight, Cpu, Database, RefreshCw, TriangleAlert } from 'lucide-vue-next'
import AppShell from '@/components/AppShell.vue'
import TelemetryChart from '@/components/TelemetryChart.vue'
import { api } from '@/lib/api'
import type { Machine, MachineContext } from '@/types'

const machines = ref<Machine[]>([])
const selected = ref('IMM-320B')
const context = ref<MachineContext | null>(null)
const rag = ref({ status: 'checking', mode: 'fake' })
const latest = computed(() => context.value?.telemetry.at(-1))

async function load() {
  const [machineRows, machineContext, ragState] = await Promise.all([
    api.machines(), api.telemetry(selected.value), api.ragStatus(),
  ])
  machines.value = machineRows
  context.value = machineContext
  rag.value = ragState
}
onMounted(load)
</script>

<template>
  <AppShell mode="engineer">
    <header class="workspace-header">
      <div><span class="eyebrow">华东工厂 · 注塑单元</span><h1>机群驾驶舱</h1><p>集中查看设备运行、报警与关键工艺趋势。</p></div>
      <div class="header-actions">
        <div class="header-status"><span><Database :size="14" />知识服务 {{ rag.mode.toUpperCase() }}</span><span class="online-dot">{{ rag.status }}</span><button class="icon-button" aria-label="刷新驾驶舱" @click="load"><RefreshCw :size="16" /></button></div>
        <RouterLink class="diagnosis-link" :to="{ path: '/engineer/diagnosis', query: { machine: selected } }">进入智能诊断<ArrowRight :size="15" /></RouterLink>
      </div>
    </header>

    <section class="machine-selector" aria-label="设备选择">
      <button v-for="machine in machines" :key="machine.id" :class="{ active: selected === machine.id }" @click="selected = machine.id; load()">
        <span :class="['status-lamp', machine.status]"></span><span><b>{{ machine.id }}</b><small>{{ machine.name.split(' · ')[1] }}</small></span><em>{{ machine.status }}</em>
      </button>
    </section>

    <section v-if="context" class="metrics-grid">
      <article class="metric panel"><span><Activity :size="15" />油温</span><b>{{ latest?.oil_temperature_c }}<small>°C</small></b><em :class="{ danger: (latest?.oil_temperature_c ?? 0) > 55 }">{{ (latest?.oil_temperature_c ?? 0) > 55 ? '越限趋势' : '稳定' }}</em></article>
      <article class="metric panel"><span><Cpu :size="15" />伺服负载</span><b>{{ latest?.servo_load_pct }}<small>%</small></b><em>{{ context.status }}</em></article>
      <article class="metric panel"><span><TriangleAlert :size="15" />活动报警</span><b>{{ context.alarm_codes.length || '00' }}</b><em>{{ context.alarm_codes.join(' / ') || '无活动报警' }}</em></article>
      <article class="metric panel"><span>累计模次</span><b>{{ context.mold_cycles.toLocaleString() }}</b><em>{{ context.active_batch }}</em></article>
      <article class="trend-panel panel"><div class="panel-heading"><span>近 30 分钟运行趋势</span><small>油温 / 伺服负载</small></div><TelemetryChart :points="context.telemetry" /></article>
    </section>
  </AppShell>
</template>
