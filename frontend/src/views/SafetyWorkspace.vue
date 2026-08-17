<script setup lang="ts">
import { AlertTriangle, BookOpenCheck, CircleCheck, LockKeyhole, ShieldCheck, UserRoundCheck } from 'lucide-vue-next'
import AppShell from '@/components/AppShell.vue'

defineProps<{ mode: 'customer' | 'engineer' }>()

const rules = [
  { index: '01', title: '只读边界', copy: '系统不连接 PLC 写通道，不自动下发温度、压力、速度或保压参数。', icon: LockKeyhole },
  { index: '02', title: '证据优先', copy: '诊断结论必须显示来源、置信度与知识版本；Fake RAG 结果会被明确标识。', icon: BookOpenCheck },
  { index: '03', title: '高风险收敛', copy: '证据不足、冲突或风险过高时隐藏具体参数，转为检查步骤与人工升级建议。', icon: AlertTriangle },
  { index: '04', title: '人工最终确认', copy: '所有维修动作与工艺调整必须由具备资质的现场人员确认并按厂内流程执行。', icon: UserRoundCheck },
]
</script>

<template>
  <AppShell :mode="mode">
    <header class="workspace-header safety-header">
      <div><span class="eyebrow">诊断安全边界</span><h1>安全规范</h1><p>本系统是诊断辅助工具，不替代设备手册、锁定挂牌制度和现场工程判断。</p></div>
      <span class="safety-seal"><ShieldCheck :size="24" /><b>只读模式</b><small>禁止写入 PLC</small></span>
    </header>

    <section class="safety-manifest panel">
      <div class="manifest-number">00</div>
      <div><span class="eyebrow">首要原则</span><h2>先确保人员与设备安全，再处理产能和质量。</h2><p>出现人员伤害风险、模具干涉、液压泄漏、电气异味或安全回路异常时，立即停止自动循环，执行现场应急与隔离流程。</p></div>
    </section>

    <section class="rule-grid">
      <article v-for="rule in rules" :key="rule.index" class="safety-rule panel">
        <span class="rule-index">{{ rule.index }}</span>
        <component :is="rule.icon" :size="23" />
        <h2>{{ rule.title }}</h2>
        <p>{{ rule.copy }}</p>
      </article>
    </section>

    <section class="escalation-strip panel">
      <div><span class="eyebrow">人工升级条件</span><h2>以下情形必须停止依赖智能建议</h2></div>
      <ul>
        <li><CircleCheck :size="14" />安全门、急停或联锁异常</li>
        <li><CircleCheck :size="14" />高压液压泄漏或电气烧灼气味</li>
        <li><CircleCheck :size="14" />模具、顶针或机械结构可能干涉</li>
        <li><CircleCheck :size="14" />知识证据缺失、过期或相互冲突</li>
      </ul>
    </section>
  </AppShell>
</template>
