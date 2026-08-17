<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { CheckCircle2, CircleDashed, Clock3, FileSearch, RefreshCw, ShieldCheck, XCircle } from 'lucide-vue-next'
import AppShell from '@/components/AppShell.vue'
import { api } from '@/lib/api'
import type { RunRecord } from '@/types'

const runs = ref<RunRecord[]>([])
const loading = ref(false)
const error = ref('')
const selected = ref<RunRecord | null>(null)
const completed = computed(() => runs.value.filter((run) => run.status === 'completed').length)
const highRisk = computed(() => runs.value.filter((run) => ['high', 'critical'].includes(run.result?.risk_level ?? '')).length)
const averageConfidence = computed(() => {
  const scored = runs.value.filter((run) => run.result?.confidence !== undefined)
  if (!scored.length) return 0
  return Math.round(scored.reduce((sum, run) => sum + (run.result?.confidence ?? 0), 0) / scored.length * 100)
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    runs.value = await api.runs()
    if (selected.value) {
      selected.value = runs.value.find((run) => run.id === selected.value?.id) ?? null
    }
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '运行记录读取失败'
  } finally {
    loading.value = false
  }
}

function stamp(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).format(new Date(value))
}

onMounted(load)
</script>

<template>
  <AppShell mode="engineer">
    <header class="workspace-header">
      <div><span class="eyebrow">诊断记录与证据追溯</span><h1>运行审计</h1><p>回看诊断任务、风险门控与证据使用情况。记录按当前租户和用户权限过滤。</p></div>
      <button class="audit-refresh" :disabled="loading" @click="load"><RefreshCw :class="{ spin: loading }" :size="15" />刷新记录</button>
    </header>

    <section class="audit-stats">
      <article class="panel"><span>最近运行</span><b>{{ runs.length.toString().padStart(2, '0') }}</b><small>最多显示 100 条</small></article>
      <article class="panel"><span>已完成</span><b>{{ completed }}</b><small>成功形成诊断结论</small></article>
      <article class="panel"><span>高风险</span><b class="danger-text">{{ highRisk }}</b><small>被安全门控标记</small></article>
      <article class="panel"><span>平均置信度</span><b>{{ averageConfidence }}%</b><small>已有结论的平均值</small></article>
    </section>

    <p v-if="error" class="error-banner">{{ error }}</p>

    <section class="audit-layout">
      <div class="audit-ledger panel">
        <div class="ledger-head"><span>运行记录</span><span>状态 / 设备 / 风险</span></div>
        <button v-for="run in runs" :key="run.id" :class="['audit-row', { selected: selected?.id === run.id }]" @click="selected = run">
          <span class="audit-status">
            <CheckCircle2 v-if="run.status === 'completed'" :size="16" />
            <XCircle v-else-if="run.status === 'failed'" :size="16" />
            <CircleDashed v-else :size="16" />
          </span>
          <span class="audit-query"><b>{{ run.query }}</b><small><Clock3 :size="11" />{{ stamp(run.created_at) }} · {{ run.id.slice(0, 8) }}</small></span>
          <span class="audit-machine">{{ run.machine_id }}</span>
          <span :class="['audit-risk', `risk-${run.result?.risk_level ?? 'pending'}`]">{{ run.result?.risk_level ?? run.status }}</span>
        </button>
        <div v-if="!runs.length && !loading" class="ledger-empty"><FileSearch :size="28" /><b>暂无运行记录</b><small>完成一次智能诊断后，记录将在此处出现。</small></div>
      </div>

      <aside class="audit-detail panel">
        <template v-if="selected">
          <span class="eyebrow">运行详情 · {{ selected.id.slice(0, 8) }}</span>
          <h2>{{ selected.machine_id }}</h2>
          <dl>
            <div><dt>运行状态</dt><dd>{{ selected.status }}</dd></div>
            <div><dt>风险等级</dt><dd>{{ selected.result?.risk_level ?? '--' }}</dd></div>
            <div><dt>置信度</dt><dd>{{ selected.result ? `${Math.round(selected.result.confidence * 100)}%` : '--' }}</dd></div>
            <div><dt>证据数量</dt><dd>{{ selected.result?.evidence.length ?? 0 }}</dd></div>
          </dl>
          <p>{{ selected.result?.answer ?? selected.error ?? '任务仍在执行，尚未形成最终结论。' }}</p>
          <div class="audit-policy"><ShieldCheck :size="14" />全过程只读，未向 PLC 写入任何参数</div>
        </template>
        <div v-else class="detail-empty"><FileSearch :size="30" /><span>选择一条运行记录查看审计详情</span></div>
      </aside>
    </section>
  </AppShell>
</template>
