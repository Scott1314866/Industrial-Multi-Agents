<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { Activity, Boxes, LogOut, Radar, ShieldCheck, UserRound } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ mode: 'customer' | 'engineer' }>()
const auth = useAuthStore()
const router = useRouter()
const root = computed(() => props.mode === 'engineer' ? '/engineer' : '/customer')

async function signOut() {
  await auth.logout()
  await router.push('/login')
}
</script>

<template>
  <div class="app-frame">
    <aside class="rail">
      <div class="brand" aria-label="MOLDWISE">
        <span class="brand-mark"><span></span><span></span><span></span></span>
        <span class="brand-copy"><b>MOLD</b>WISE<small>注塑设备智能运维平台</small></span>
      </div>

      <nav aria-label="主导航">
        <RouterLink :to="root" class="nav-item" exact-active-class="is-active">
          <Radar :size="18" /><span>{{ mode === 'engineer' ? '机群驾驶舱' : '设备中心' }}</span>
        </RouterLink>
        <RouterLink :to="`${root}/diagnosis`" class="nav-item" active-class="is-active">
          <Activity :size="18" /><span>智能诊断</span>
        </RouterLink>
        <RouterLink v-if="mode === 'engineer'" :to="`${root}/audit`" class="nav-item" active-class="is-active">
          <Boxes :size="18" /><span>运行审计</span>
        </RouterLink>
        <RouterLink :to="`${root}/safety`" class="nav-item" active-class="is-active">
          <ShieldCheck :size="18" /><span>安全规范</span>
        </RouterLink>
      </nav>

      <div class="rail-foot">
        <div class="identity">
          <span class="avatar"><UserRound :size="16" /></span>
          <span><b>{{ auth.user?.display_name }}</b><small>{{ mode === 'engineer' ? '授权工程师' : '客户工作区' }}</small></span>
        </div>
        <button class="icon-button" title="退出登录" @click="signOut"><LogOut :size="17" /></button>
      </div>
    </aside>

    <main class="workspace"><slot /></main>
  </div>
</template>
