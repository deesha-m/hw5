import type { AgentEvent, Role } from './api'
import { CREW, ROLES, crew, shortArgs, toolVerb } from './crew'

export type AgentStatus = 'idle' | 'working' | 'done' | 'failed'

export interface AgentState {
  role: Role
  status: AgentStatus
  line: string // what the speech bubble says right now
  currentTools: string[]
  toolsUsed: string[] // MCP tools, in first-use order
  handedTo: Role[]
  delegatedBy: string | null
  steps: number
  blocked: string[]
  summary: string | null
  reportStatus: string | null
  startedAt: string | null
  endedAt: string | null
}

export interface Edge {
  from: Role
  to: Role
  state: 'active' | 'done'
}

export interface RunView {
  runId: string | null
  agents: Record<Role, AgentState>
  edges: Edge[]
  events: AgentEvent[]
  finished: boolean
  startedAt: string | null
  endedAt: string | null
}

function blank(role: Role): AgentState {
  return {
    role, status: 'idle', line: CREW[role].idle, currentTools: [], toolsUsed: [], handedTo: [],
    delegatedBy: null, steps: 0, blocked: [], summary: null, reportStatus: null, startedAt: null, endedAt: null,
  }
}

function taskOf(said: string | null): string {
  if (!said) return ''
  const i = said.indexOf('Task:')
  return (i >= 0 ? said.slice(i + 5) : said).trim()
}

/** The most recent top-level run for this ticket (events are oldest first). */
export function latestRunId(events: AgentEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i]
    if (e.event === 'run_start' && !e.parent_agent) return e.team_run_id
  }
  return null
}

/** Replays one run's events into each agent's current state and the delegation edges. */
export function buildRun(allEvents: AgentEvent[], runId: string | null): RunView {
  const agents = Object.fromEntries(ROLES.map(r => [r, blank(r)])) as Record<Role, AgentState>
  const edges = new Map<string, Edge>()
  const events = runId ? allEvents.filter(e => e.team_run_id === runId) : []
  let finished = false

  for (const e of events) {
    const role = e.agent as Role
    const a = agents[role]
    if (!a) continue
    switch (e.event) {
      case 'run_start': {
        a.status = 'working'
        a.startedAt = e.timestamp
        a.delegatedBy = e.parent_agent
        a.line = e.parent_agent ? `Picked up from ${crew(e.parent_agent).name}: ${taskOf(e.said)}` : `New ticket on the desk. ${taskOf(e.said)}`
        if (e.parent_agent) edges.set(`${e.parent_agent}>${role}`, { from: e.parent_agent as Role, to: role, state: 'active' })
        break
      }
      case 'model_response': {
        a.steps += 1
        const calls = e.tools_called
        a.currentTools = calls.map(c => c.tool)
        const handoff = calls.find(c => c.tool === 'delegate')
        if (handoff && typeof handoff.args === 'object') {
          const to = String(handoff.args.to) as Role
          if (!a.handedTo.includes(to)) a.handedTo.push(to)
          a.line = `Handing to ${crew(to).name}: ${String(handoff.args.task ?? '')}`
        } else if (calls.length) {
          const c = calls[0]
          a.line = c.tool === 'final_result'
            ? 'Writing up my report…'
            : `${toolVerb(c.tool)}… ${shortArgs(c.args)}`.trim() + (calls.length > 1 ? `  (+${calls.length - 1} more)` : '')
        } else if (e.said) {
          a.line = e.said
        }
        for (const c of calls) {
          if (c.tool !== 'delegate' && c.tool !== 'final_result' && !a.toolsUsed.includes(c.tool)) a.toolsUsed.push(c.tool)
        }
        break
      }
      case 'tool_results': {
        a.currentTools = []
        for (const r of e.tool_results) {
          if (r.outcome === 'blocked') a.blocked.push(`${r.tool}: ${r.result.replace(/^\{"blocked": true, "reason": "/, '').replace(/"\}$/, '')}`)
        }
        break
      }
      case 'run_end': {
        a.status = e.stop_reason === 'final_output' ? 'done' : 'failed'
        a.endedAt = e.timestamp
        a.currentTools = []
        a.summary = e.said
        a.reportStatus = e.report_status
        a.line = e.said ?? (e.error ? `Stopped: ${e.error}` : 'Finished.')
        if (e.parent_agent) edges.set(`${e.parent_agent}>${role}`, { from: e.parent_agent as Role, to: role, state: 'done' })
        if (!e.parent_agent) finished = true
        break
      }
    }
  }
  return {
    runId, agents, edges: [...edges.values()], events, finished,
    startedAt: events[0]?.timestamp ?? null,
    endedAt: finished ? events[events.length - 1]?.timestamp ?? null : null,
  }
}
