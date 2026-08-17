import type { GraphResult, Machine, MachineContext, RunRecord, User } from '@/types'

const API = '/api/v1'
let accessToken = ''

export function setAccessToken(token: string) {
  accessToken = token
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  const response = await fetch(`${API}${path}`, { ...init, headers, credentials: 'include' })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(error.detail?.message ?? error.detail?.code ?? '请求失败')
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  async login(email: string, password: string) {
    const token = await request<{ access_token: string }>('/auth/login', {
      method: 'POST', body: JSON.stringify({ email, password }),
    })
    setAccessToken(token.access_token)
    return token
  },
  async refresh() {
    const token = await request<{ access_token: string }>('/auth/refresh', { method: 'POST' })
    setAccessToken(token.access_token)
  },
  me: () => request<User>('/auth/me'),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  machines: () => request<Machine[]>('/machines'),
  telemetry: (id: string) => request<MachineContext>(`/machines/${id}/telemetry`),
  ragStatus: () => request<{ status: string; mode: string }>('/rag/status'),
  agents: () => request<Array<{ id: string; name: string; status: string; accent: string }>>('/agents'),
  async createConversation(machineId: string, title: string) {
    return request<{ id: string }>('/conversations', {
      method: 'POST', body: JSON.stringify({ machine_id: machineId, title }),
    })
  },
  async createRun(conversationId: string, query: string) {
    return request<{ id: string }>(`/conversations/${conversationId}/runs`, {
      method: 'POST', body: JSON.stringify({ query }),
    })
  },
  run: (runId: string) => request<{ result: GraphResult | null; status: string }>(`/runs/${runId}`),
  runs: () => request<RunRecord[]>('/runs'),
}

export async function streamRun(
  runId: string,
  onEvent: (event: { type: string; data: RunEventData }) => void,
): Promise<void> {
  const response = await fetch(`${API}/runs/${runId}/events`, {
    headers: { Authorization: `Bearer ${accessToken}` }, credentials: 'include',
  })
  if (!response.ok || !response.body) throw new Error('无法建立诊断事件流')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      const lines = frame.split('\n')
      const type = lines.find((line) => line.startsWith('event:'))?.slice(6).trim() ?? 'message'
      const raw = lines.find((line) => line.startsWith('data:'))?.slice(5).trim()
      if (raw) onEvent({ type, data: JSON.parse(raw) as RunEventData })
    }
  }
}

export interface RunEventData {
  id: string
  run_id: string
  type: string
  node?: string
  message: string
  data: Record<string, unknown>
}
