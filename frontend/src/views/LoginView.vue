<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, LockKeyhole, Orbit, ShieldCheck } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const email = ref('engineer@moldwise.local')
const password = ref('Engineer123!')
const busy = ref(false)
const error = ref('')

async function login() {
  busy.value = true
  error.value = ''
  try {
    await auth.login(email.value, password.value)
    await router.push(auth.user?.role === 'customer' ? '/customer' : '/engineer')
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '登录失败'
  } finally {
    busy.value = false
  }
}

function useCustomer() {
  email.value = 'customer@moldwise.local'
  password.value = 'Customer123!'
}
</script>

<template>
  <main class="login-page">
    <div class="login-grid" aria-hidden="true"></div>
    <section class="login-manifesto">
      <span class="eyebrow"><Orbit :size="14" /> 注塑设备智能运维平台</span>
      <h1>让每一次<br /><em>停机之前</em><br />都有迹可循。</h1>
      <p>面向注塑设备的可追溯智能诊断。机器趋势、工程经验与知识凭证，在每个受控工作流中汇合。</p>
      <div class="manifesto-stats">
        <span><b>04</b><small>专业分析模块</small></span>
        <span><b>00</b><small>PLC 写入操作</small></span>
        <span><b>100%</b><small>运行过程可追溯</small></span>
      </div>
    </section>

    <section class="login-card">
      <div class="brand login-brand"><span class="brand-mark"><span></span><span></span><span></span></span><span class="brand-copy"><b>MOLD</b>WISE<small>注塑设备智能运维平台</small></span></div>
      <div class="login-heading"><span>企业账号登录</span><h2>进入工作台</h2><p>访问已授权设备、诊断和运行记录。</p></div>
      <form @submit.prevent="login">
        <label>企业邮箱<input v-model="email" type="email" autocomplete="username" /></label>
        <label>访问密码<input v-model="password" type="password" autocomplete="current-password" /></label>
        <p v-if="error" class="error-banner">{{ error }}</p>
        <button class="primary-action" :disabled="busy"><LockKeyhole :size="17" />{{ busy ? '正在验证…' : '安全登录' }}<ArrowRight :size="17" /></button>
      </form>
      <button class="customer-switch" @click="useCustomer">切换为客户演示账号</button>
      <p class="security-note"><ShieldCheck :size="14" />会话受 RBAC 与设备级权限保护</p>
    </section>
  </main>
</template>
