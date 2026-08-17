<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowUp, BookOpen, Bot, LoaderCircle, ShieldAlert, Wrench } from 'lucide-vue-next'
import { api, streamRun } from '@/lib/api'
import type { GraphResult, RunEvent } from '@/types'
import MachineSpine from './MachineSpine.vue'

const props = defineProps<{ machineId: string; customer?: boolean }>()
const query = ref('')
const busy = ref(false)
const events = ref<RunEvent[]>([])
const result = ref<GraphResult | null>(null)
const error = ref('')
const suggestions = computed(() => props.customer
  ? ['设备报警 H-08，应该怎么处理？', '产品出现飞边，请帮我分析', '这台设备什么时候需要保养？']
  : ['分析当前设备报警与油温趋势', '飞边集中在浇口附近，给出排查顺序', '结合模次制定计划维护清单'])
const riskLabels: Record<GraphResult['risk_level'], string> = {
  low: '低风险', medium: '中风险', high: '高风险', critical: '严重风险',
}

async function submit(text?: string) {
  const prompt = (text ?? query.value).trim()
  if (!prompt || busy.value) return
  query.value = prompt
  busy.value = true
  events.value = []
  result.value = null
  error.value = ''
  try {
    const conversation = await api.createConversation(props.machineId, prompt.slice(0, 28))
    const run = await api.createRun(conversation.id, prompt)
    await streamRun(run.id, ({ data }) => {
      events.value.push(data as RunEvent)
      if (data.type === 'run.completed' || data.type === 'run.input_required') {
        result.value = data.data as unknown as GraphResult
      }
    })
    if (!result.value) {
      const final = await api.run(run.id)
      result.value = final.result
    }
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '诊断请求失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="analysis-console panel">
    <div class="console-topline">
      <span><Bot :size="16" /> 智能诊断台</span>
      <span class="safety-chip"><ShieldAlert :size="13" /> 只读 · 不写入 PLC</span>
    </div>

    <div class="console-grid">
      <MachineSpine :events="events" :active="busy" />
      <div class="dialog-stage">
        <div v-if="!result && !busy && !error" class="empty-state">
          <span class="empty-glyph"><Wrench :size="28" /></span>
          <h2>{{ customer ? '描述设备现象' : '启动一次可追溯诊断' }}</h2>
          <p>系统将结合设备趋势、专业分析模块与知识证据形成判断，不会自动修改任何设备参数。</p>
          <div class="suggestions">
            <button v-for="item in suggestions" :key="item" @click="submit(item)">{{ item }}</button>
          </div>
        </div>

        <div v-if="busy" class="running-state">
          <LoaderCircle class="spin" :size="22" />
          <span><b>正在分析设备信息</b><small>{{ events.at(-1)?.message ?? '读取设备上下文…' }}</small></span>
        </div>

        <div v-if="result" class="result-state">
          <div class="result-meta">
            <span :class="['risk-badge', `risk-${result.risk_level}`]">{{ riskLabels[result.risk_level] }}</span>
            <span>置信度 {{ Math.round(result.confidence * 100) }}%</span>
          </div>
          <div class="answer">{{ result.answer }}</div>
          <div v-if="result.warnings?.length" class="warning-stack">
            <p v-for="warning in result.warnings" :key="warning"><ShieldAlert :size="14" />{{ warning }}</p>
          </div>
          <div v-if="result.evidence?.length" class="evidence-strip">
            <article v-for="item in result.evidence" :key="item.document_id">
              <BookOpen :size="15" /><span><b>{{ item.title }}</b><small>{{ item.section }} · {{ Math.round(item.score * 100) }}%</small></span>
            </article>
          </div>
        </div>
        <p v-if="error" class="error-banner">{{ error }}</p>

        <form class="prompt-bar" @submit.prevent="submit()">
          <textarea v-model="query" rows="1" :placeholder="customer ? '请描述报警、异响或产品缺陷…' : '输入报警、缺陷、工艺或维护问题…'" @keydown.enter.exact.prevent="submit()"></textarea>
          <button :disabled="busy || !query.trim()" aria-label="发送诊断请求"><ArrowUp :size="18" /></button>
        </form>
      </div>
    </div>
  </section>
</template>
