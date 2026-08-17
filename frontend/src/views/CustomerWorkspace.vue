<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ArrowRight, CircleCheck, Headphones, ShieldCheck } from 'lucide-vue-next'
import AppShell from '@/components/AppShell.vue'
import TelemetryChart from '@/components/TelemetryChart.vue'
import { api } from '@/lib/api'
import type { Machine, MachineContext } from '@/types'

const machines = ref<Machine[]>([])
const selected = ref('IMM-240A')
const context = ref<MachineContext | null>(null)
const latest = computed(() => context.value?.telemetry.at(-1))
async function load() { machines.value = await api.machines(); context.value = await api.telemetry(selected.value) }
onMounted(load)
</script>

<template>
  <AppShell mode="customer">
    <header class="workspace-header customer-header">
      <div><span class="eyebrow">客户设备中心</span><h1>设备运行中心</h1><p>查看设备状态、批次和关键质量趋势。</p></div>
      <div class="header-actions"><button class="support-button"><Headphones :size="17" />联系授权售后</button><RouterLink class="diagnosis-link" :to="{ path: '/customer/diagnosis', query: { machine: selected } }">进入智能诊断<ArrowRight :size="15" /></RouterLink></div>
    </header>
    <section class="customer-overview">
      <div class="machine-hero panel">
        <select v-model="selected" @change="load"><option v-for="machine in machines" :key="machine.id" :value="machine.id">{{ machine.name }}</option></select>
        <div v-if="context" class="hero-machine">
          <span class="machine-orbit"><span></span><b>{{ context.machine_id }}</b></span>
          <div><span class="eyebrow">当前状态</span><h2>{{ context.status === 'running' ? '设备运行稳定' : '检测到需要关注的趋势' }}</h2><p>当前批次 {{ context.active_batch }} · 累计 {{ context.mold_cycles.toLocaleString() }} 模次</p></div>
        </div>
        <TelemetryChart v-if="context" :points="context.telemetry" />
      </div>
      <div class="customer-facts">
        <article class="panel"><CircleCheck :size="20" /><span><small>质量评分</small><b>{{ latest?.quality_score ?? '--' }}</b></span></article>
        <article class="panel"><ShieldCheck :size="20" /><span><small>安全策略</small><b>只读建议</b></span></article>
      </div>
    </section>
  </AppShell>
</template>
