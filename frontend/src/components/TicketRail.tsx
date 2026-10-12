import type { PendingApproval, TicketCard } from '../api'
import { STATUS_LABEL, TICKET_TYPE } from '../crew'

interface Props {
  tickets: TicketCard[]
  approvals: PendingApproval[]
  selected: number | null
  justResolved: Set<number>
  onSelect: (id: number) => void
  onRun: (id: number) => void
  busy: boolean
}

export function TicketRail({ tickets, approvals, selected, justResolved, onSelect, onRun, busy }: Props) {
  return (
    <aside className="rail">
      <div className="rail-head">
        <span className="kicker">Ticket spike</span>
        <span className="count">{tickets.filter(t => t.state === 'open').length} open</span>
      </div>
      {tickets.length === 0 && <div className="rail-empty">Waiting for the backend…</div>}
      {tickets.map(t => {
        const type = TICKET_TYPE[t.type] ?? { label: t.type, icon: '🎫' }
        const needsSign = approvals.some(a => a.ticket_id === t.ticket_id)
        const isSel = selected === t.ticket_id
        const stamp = t.running ? 'working' : t.state === 'resolved' ? 'resolved' : needsSign ? 'sign' : null
        return (
          <article
            key={t.ticket_id}
            className={`stub ${isSel ? 'selected' : ''} ${t.state}`}
            onClick={() => onSelect(t.ticket_id)}
            role="button"
            tabIndex={0}
            onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onSelect(t.ticket_id)}
          >
            <div className="stub-top">
              <span className="stub-no">#{t.ticket_id}</span>
              <span className="stub-type"><span aria-hidden>{type.icon}</span> {type.label}</span>
            </div>
            <h3 className="stub-subject">{t.subject}</h3>
            <div className="stub-from">from <b>{t.requester}</b></div>
            <div className="stub-perf" aria-hidden />
            <div className="stub-foot">
              <span className={`dbstatus s-${t.status}`}>{t.status.replace('_', ' ')}</span>
              {t.last_report_status && !t.running && t.state === 'open' && (
                <span className="last">Last run: {STATUS_LABEL[t.last_report_status] ?? t.last_report_status}</span>
              )}
            </div>
            {stamp && (
              <span className={`stamp stamp-${stamp} ${justResolved.has(t.ticket_id) ? 'thunk' : ''}`}>
                {stamp === 'resolved' ? 'Resolved' : stamp === 'sign' ? 'Sign here' : 'On it…'}
              </span>
            )}
            {isSel && (
              <button
                className="run-btn"
                disabled={busy || t.running}
                onClick={e => { e.stopPropagation(); onRun(t.ticket_id) }}
              >
                {t.running ? 'Team is working…' : t.state === 'resolved' || t.last_run_id ? 'Run the team again' : 'Hand it to the Boss'}
                <span aria-hidden> →</span>
              </button>
            )}
          </article>
        )
      })}
      <p className="rail-hint">Pick a ticket, then hand it to the Boss. The team works it live on the floor.</p>
    </aside>
  )
}
