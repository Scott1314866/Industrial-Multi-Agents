export type Role = 'customer' | 'engineer' | 'admin'

export interface User {
  id: string
  email: string
  display_name: string
  role: Role
  tenant_id: string
}

export interface Machine {
  id: string
  name: string
  status: 'running' | 'warning' | 'stopped' | 'maintenance'
}

export interface TelemetryPoint {
  timestamp: string
  oil_temperature_c: number
  injection_pressure_mpa: number
  injection_speed_mm_s: number
  cycle_time_s: number
  servo_load_pct: number
  quality_score: number
}

export interface MachineContext {
  machine_id: string
  model: string
  status: Machine['status']
  alarm_codes: string[]
  mold_cycles: number
  active_batch: string
  telemetry: TelemetryPoint[]
}

export interface RunEvent {
  id: string
  run_id: string
  type: string
  timestamp: string
  node?: string
  message: string
  data: Record<string, unknown>
}

export interface GraphResult {
  answer: string
  status: string
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  confidence: number
  findings: Array<Record<string, unknown>>
  evidence: Array<{
    document_id: string
    title: string
    section?: string
    snippet: string
    score: number
  }>
  warnings: string[]
}

export interface RunRecord {
  id: string
  conversation_id: string
  machine_id: string
  status: string
  query: string
  result: GraphResult | null
  error: string | null
  created_at: string
  updated_at: string
}
