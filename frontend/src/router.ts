import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/customer', name: 'customer-dashboard', component: () => import('@/views/CustomerWorkspace.vue') },
    { path: '/customer/diagnosis', name: 'customer-diagnosis', component: () => import('@/views/DiagnosisWorkspace.vue'), props: { mode: 'customer' } },
    { path: '/customer/safety', name: 'customer-safety', component: () => import('@/views/SafetyWorkspace.vue'), props: { mode: 'customer' } },
    { path: '/engineer', name: 'engineer-dashboard', component: () => import('@/views/EngineerWorkspace.vue') },
    { path: '/engineer/diagnosis', name: 'engineer-diagnosis', component: () => import('@/views/DiagnosisWorkspace.vue'), props: { mode: 'engineer' } },
    { path: '/engineer/audit', name: 'engineer-audit', component: () => import('@/views/AuditWorkspace.vue') },
    { path: '/engineer/safety', name: 'engineer-safety', component: () => import('@/views/SafetyWorkspace.vue'), props: { mode: 'engineer' } },
    { path: '/:pathMatch(.*)*', redirect: '/engineer' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.restore()
  if (!to.meta.public && !auth.authenticated) return '/login'
  if (to.name === 'login' && auth.authenticated) {
    return auth.user?.role === 'customer' ? '/customer' : '/engineer'
  }
  if (to.path.startsWith('/engineer') && auth.user?.role === 'customer') return '/customer'
})

export default router
