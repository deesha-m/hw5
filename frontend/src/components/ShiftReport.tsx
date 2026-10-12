import type { AgentReport, Payment, RunStatus } from '../api'
import { CREW, ROLES, STATUS_LABEL, money, toolVerb } from '../crew'
import type { RunView } from '../desk'

function duration(a: string | null, b: string | null): string | null {
  if (!a || !b) return null
  const s = Math.max(0, Math.round((Date.parse(b) - Date.parse(a)) / 1000))
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`
}

interface Props {
  run: RunView
  report: AgentReport | null
  runStatus: RunStatus | null
  requester: string | null
  payments: Payment[]
}

export function ShiftReport({ run, report, runStatus, requester, payments }: Props) {
  if (!run.runId) {
    return <div className="wire-empty">No shift report yet. Run the team on this ticket and each agent's write-up lands here.</div>
  }
  if (!run.finished) {
    return <div className="wire-empty">The team is still working. The shift report fills in the moment the Boss signs off.</div>
  }
  const worked = ROLES.filter(r => run.agents[r].status !== 'idle')
  const skipped = ROLES.filter(r => run.agents[r].status === 'idle')
  const stats = runStatus?.team_run_id === run.runId ? runStatus.result : null
  // Payments the agents asked for that a human has since signed.
  const signed = (report?.approvals_needed ?? []).flatMap(a =>
    payments.filter(p => a.pay_kind && p.kind === a.pay_kind && p.ref_id === a.pay_ref_id),
  )

  return (
    <div className="report">
      {report && (
        <div className={`verdict v-${report.status}`}>
          <div className="verdict-top">
            <span className="kicker">The Boss's call</span>
            {signed.length > 0
              ? <span className="pill p-done">Signed &amp; paid</span>
              : <span className={`pill p-${report.status}`}>{STATUS_LABEL[report.status] ?? report.status}</span>}
          </div>
          <p className="verdict-text">{report.summary}</p>
          {signed.map(p => (
            <div key={p.payment_id} className="signed">
              ✓ Signed by <b>{p.approved_by}</b>: {money(p.amount)} paid ({p.kind} {p.ref_id}, payment #{p.payment_id})
            </div>
          ))}
          <div className="verdict-meta">
            <span>{worked.length} of 5 agents worked it</span>
            {duration(run.startedAt, run.endedAt) && <span>{duration(run.startedAt, run.endedAt)} on the floor</span>}
            {stats && <span>{stats.delegations} hand-offs · {stats.tool_calls} tool calls · {(stats.input_tokens + stats.output_tokens).toLocaleString()} tokens</span>}
          </div>
        </div>
      )}

      <div className="crew-cards">
        {worked.map(role => {
          const a = run.agents[role]
          const c = CREW[role]
          return (
            <div key={role} className="crew-card" style={{ ['--c' as string]: c.color }}>
              <div className="crew-card-head">
                <span className="avatar sm" aria-hidden>{c.glyph}</span>
                <b>{c.name}</b>
                {a.reportStatus && <span className={`pill p-${a.reportStatus}`}>{STATUS_LABEL[a.reportStatus] ?? a.reportStatus}</span>}
              </div>
              <p>{a.summary ?? 'No report.'}</p>
              <div className="crew-card-tools">
                {a.handedTo.map(h => (
                  <span key={h} className="chip chip-hand" style={{ ['--c' as string]: CREW[h].color }}>➜ {CREW[h].name}</span>
                ))}
                {a.toolsUsed.map(t => <span key={t} className="chip" title={toolVerb(t)}>{t}</span>)}
              </div>
              {a.blocked.length > 0 && <div className="guard">⛔ Guardrail stopped: {a.blocked.join('; ')}</div>}
            </div>
          )
        })}
        {skipped.length > 0 && (
          <div className="crew-skipped">
            Not needed on this ticket: {skipped.map(r => CREW[r].name).join(', ')}
          </div>
        )}
      </div>

      {report && report.facts.length > 0 && (
        <details className="facts" open>
          <summary>Facts the decision rests on</summary>
          <ul>
            {report.facts.map((f, i) => (
              <li key={i}>{f.statement} <span className="src">{f.source}</span></li>
            ))}
          </ul>
        </details>
      )}

      {report?.customer_message && (
        <div className="letter">
          <span className="letter-stamp">Draft · not sent</span>
          <div className="letter-to">To: {requester ?? 'the requester'}</div>
          <p>{report.customer_message}</p>
          <div className="letter-sign">— The Campus Customs team</div>
        </div>
      )}

      {report && report.next_steps.length > 0 && (
        <div className="next">
          <span className="kicker">Next up</span>
          <ul>{report.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ul>
        </div>
      )}
    </div>
  )
}
