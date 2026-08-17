<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Activity, Cpu, Gauge, RefreshCw, TriangleAlert } from 'lucide-vue-next'
import AppShell from '@/components/AppShell.vue'
import AnalysisConsole from '@/components/AnalysisConsole.vue'
import { api } from '@/lib/api'
import type { Machine, MachineContext } from '@/types'

const props = defineProps<{ mode: 'customer' | 'engineer' }>()
const route = useRoute()
const router = useRouter()
const machines = ref<Machine[]>([])
const selected = ref('')
const context = ref<MachineContext | null>(null)
const loading = ref(false)
const error = ref('')
const latest = computed(() => context.value?.telemetry.at(-1))

async function loadMachines() {
  machines.value = await api.machines()
  const requested = typeof route.query.machine === 'string' ? route.query.machine : ''
  const fallback = props.mode === 'engineer' ? 'IMM-320B' : 'IMM-240A'
  selected.value = machines.value.some((machine) => machine.id === requested)
    ? requested
    : machines.value.some((machine) => machine.id === fallback) ? fallback : machines.value[0]?.id ?? ''
}

async function loadContext() {
  if (!selected.value) return
  loading.value = true
  error.value = ''
  try {
    context.value = await api.telemetry(selected.value)
    await router.replace({ query: { ...route.query, machine: selected.value } })
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '无法读取设备上下文'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    await loadMachines()
    await loadContext()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '诊断工作区加载失败'
  }
})
</script>

<template>
  <AppShell :mode="mode">
    <header class="workspace-header diagnosis-header">
      <div>
        <span class="eyebrow">设备诊断工作台</span>
        <h1>智能诊断</h1>
        <p>选择设备并描述报警、缺陷或工艺异常。每次结论都经过证据汇总与安全门控。</p>
      </div>
      <div class="diagnosis-machine-select">
        <label for="diagnosis-machine">目标设备</label>
        <select id="diagnosis-machine" v-model="selected" @change="loadContext">
          <option v-for="machine in machines" :key="machine.id" :value="machine.id">
            {{ machine.id }} · {{ machine.status }}
          </option>
        </select>
        <button class="icon-button" aria-label="刷新设备上下文" :disabled="loading" @click="loadContext">
          <RefreshCw :class="{ spin: loading }" :size="16" />
        </button>
      </div>
    </header>

    <p v-if="error" class="error-banner">{{ error }}</p>

    <section v-if="context" class="context-ribbon" aria-label="当前设备上下文">
      <article><span><Activity :size="14" />状态</span><b :class="`signal-${context.status}`">{{ context.status }}</b></article>
      <article><span><TriangleAlert :size="14" />报警</span><b>{{ context.alarm_codes.join(' / ') || '无活动报警' }}</b></article>
      <article><span><Gauge :size="14" />注射压力</span><b>{{ latest?.injection_pressure_mpa ?? '--' }} MPa</b></article>
      <article><span><Cpu :size="14" />伺服负载</span><b>{{ latest?.servo_load_pct ?? '--' }}%</b></article>
    </section>

    <AnalysisConsole v-if="selected" :machine-id="selected" :customer="mode === 'customer'" />
  </AppShell>
</template>
