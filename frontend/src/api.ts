// Talks to the FastAPI backend from Problem 7 (backend/main.py).
export const API_BASE: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type Role = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface TicketCard {
  ticket_id: number
  type: string
  requester: string
  subject: string
  status: string
  state: 'open' | 'resolved'
  created_at: string
  running: boolean
  last_run_id: string | null
  last_report_status: string | null
  last_summary: string | null
}

export interface Fact { statement: string; source: string }
export interface ApprovalRequest {
  kind: string
  reference: string
  amount: number | null
  reason: string
  pay_kind?: 'invoice' | 'rent' | null
  pay_ref_id?: number | null
}
export interface AgentReport {
  role: Role
  ticket_ids: number[]
  status: string
  summary: string
  facts: Fact[]
  actions_taken: string[]
  approvals_needed: ApprovalRequest[]
  customer_message: string | null
  next_steps: string[]
}

export interface TicketDetail {
  ticket: {
    ticket_id: number
    type: string
    requester: string
    subject: string
    sku: string | null
    size: string | null
    qty: number | null
    lease_id: number | null
    invoice_id: number | null
    status: string
    notes: string | null
    created_at: string
    as_of: string
  }
  last_run_id: string | null
  last_report: AgentReport | null
  running: boolean
}

export interface ToolCall { tool_call_id: string; tool: string; args: Record<string, unknown> | string }
export interface ToolResult { tool_call_id: string; tool: string; outcome: 'ok' | 'error' | 'blocked'; result: string }

export interface AgentEvent {
  id: number
  timestamp: string
  team_run_id: string
  ticket_id: number | null
  agent: string
  parent_agent: string | null
  chain: string[]
  step: number
  event: 'run_start' | 'model_response' | 'tool_results' | 'run_end' | 'db_reset'
  said: string | null
  tools_called: ToolCall[]
  tool_results: ToolResult[]
  report_status: string | null
  stop_reason: string | null
  error: string | null
}
export interface EventsPage { events: AgentEvent[]; last_id: number }

export interface RunStatus {
  team_run_id: string
  ticket_id: number | null
  state: 'running' | 'finished' | 'failed'
  started_at: string
  finished_at: string | null
  result: {
    report: AgentReport | null
    stop_reason: string
    error: string | null
    requests: number
    tool_calls: number
    input_tokens: number
    output_tokens: number
    delegations: number
  } | null
  error: string | null
}

export interface PendingApproval {
  ticket_id: number | null
  team_run_id: string
  pay_kind: 'invoice' | 'rent'
  pay_ref_id: number
  amount: number
  payee: string
  reference: string
  reason: string
  requested_by: string
}

export interface Payment {
  payment_id: number
  kind: string
  ref_id: number | null
  amount: number
  account: string
  paid_at: string
  approved_by: string
}
export interface CashView {
  account: string
  balance: number
  balance_date: string
  as_of: string
  low_cash: boolean
  payments: Payment[]
}

export interface ApproveResult {
  payment: Payment
  balance_before: number
  balance_after: number
  marked: string
  ticket_note: string | null
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep the status text */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => call<{ ok: boolean; database: string }>('/api/health'),
  tickets: () => call<TicketCard[]>('/api/tickets'),
  ticket: (id: number) => call<TicketDetail>(`/api/tickets/${id}`),
  run: (id: number) => call<RunStatus>(`/api/tickets/${id}/run`, { method: 'POST' }),
  runStatus: (runId: string) => call<RunStatus>(`/api/runs/${runId}`),
  events: (params: { after?: number; ticket_id?: number; team_run_id?: string }) => {
    const q = new URLSearchParams()
    if (params.after !== undefined) q.set('after', String(params.after))
    if (params.ticket_id !== undefined) q.set('ticket_id', String(params.ticket_id))
    if (params.team_run_id) q.set('team_run_id', params.team_run_id)
    q.set('limit', '500')
    return call<EventsPage>(`/api/events?${q}`)
  },
  approvals: () => call<PendingApproval[]>('/api/approvals'),
  approve: (body: { pay_kind: string; pay_ref_id: number; amount: number; approved_by: string; ticket_id: number | null }) =>
    call<ApproveResult>('/api/approvals', { method: 'POST', body: JSON.stringify(body) }),
  cash: () => call<CashView>('/api/cash'),
  reset: () => call<{ reset_at: string; sha256: string; events_after: number }>('/api/reset', { method: 'POST' }),
}
