import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api, setAccessToken } from '@/lib/api'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const ready = ref(false)
  const authenticated = computed(() => Boolean(user.value))

  async function login(email: string, password: string) {
    await api.login(email, password)
    user.value = await api.me()
  }

  async function restore() {
    if (ready.value) return
    try {
      await api.refresh()
      user.value = await api.me()
    } catch {
      setAccessToken('')
      user.value = null
    } finally {
      ready.value = true
    }
  }

  async function logout() {
    await api.logout().catch(() => undefined)
    setAccessToken('')
    user.value = null
  }

  return { user, ready, authenticated, login, restore, logout }
})

