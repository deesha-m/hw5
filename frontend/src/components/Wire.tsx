import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import type { AgentEvent } from '../api'
import { STATUS_LABEL, crew, shortArgs, toolVerb } from '../crew'

function clock(ts: string): string {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}

function Line({ e }: { e: AgentEvent }) {
  const c = crew(e.agent)
  const depth = Math.max(0, e.chain.length - 1)
  let body: ReactNode = null

  if (e.event === 'run_start') {
    const task = (e.said ?? '').replace(/^Delegated by [^.]+\.\s*Task:\s*/s, '')
    body = (
      <>
        <span className="verb">{e.parent_agent ? `picked up from ${crew(e.parent_agent).name}` : 'took the ticket'}</span>
        <span className="quote">{task}</span>
      </>
    )
  } else if (e.event === 'model_response') {
    const calls = e.tools_called
    body = calls.length ? (
      <span className="chips">
        {calls.map(t =>
          t.tool === 'delegate' && typeof t.args === 'object' ? (
            <span key={t.tool_call_id} className="chip chip-hand" style={{ ['--c' as string]: crew(String(t.args.to)).color }}>
              ➜ {crew(String(t.args.to)).name}
            </span>
          ) : (
            <span key={t.tool_call_id} className="chip" title={JSON.stringify(t.args)}>
              {t.tool}<span className="args">({shortArgs(t.args)})</span>
            </span>
          ),
        )}
      </span>
    ) : (
      <span className="quote">{e.said ?? 'Thinking…'}</span>
    )
  } else if (e.event === 'tool_results') {
    body = (
      <span className="chips">
        {e.tool_results.map(r => (
          <span key={r.tool_call_id} className={`chip res res-${r.outcome}`} title={r.result}>
            {r.outcome === 'ok' ? '✓' : r.outcome === 'blocked' ? '⛔' : '!'} {r.tool === 'delegate' ? 'teammate replied' : toolVerb(r.tool).toLowerCase()}
          </span>
        ))}
      </span>
    )
  } else if (e.event === 'run_end') {
    body = (
      <>
        <span className={`pill p-${e.report_status ?? 'failed'}`}>{e.report_status ? STATUS_LABEL[e.report_status] ?? e.report_status : e.stop_reason}</span>
        <span className="quote">{e.said ?? e.error}</span>
      </>
    )
  }

  return (
    <li className={`wire-line ev-${e.event}`} style={{ ['--c' as string]: c.color, ['--d' as string]: depth }}>
      <time>{clock(e.timestamp)}</time>
      <span className="who"><span aria-hidden>{c.glyph}</span> {c.name}</span>
      <span className="what">{body}</span>
    </li>
  )
}

export function Wire({ events, live }: { events: AgentEvent[]; live: boolean }) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = box.current
    if (live && el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [events.length, live])

  if (!events.length) {
    return <div className="wire-empty">The wire is quiet. Start the team on a ticket and every hand-off, tool call and answer shows up here, live.</div>
  }
  return (
    <div className="wire-scroll" ref={box}>
      <ol className="wire-list">
        {events.map(e => <Line key={e.id} e={e} />)}
      </ol>
    </div>
  )
}
