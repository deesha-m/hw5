import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { API_BASE, api } from './api'
import type { AgentEvent, CashView, PendingApproval, RunStatus, TicketCard, TicketDetail } from './api'
import { Cheque } from './components/Cheque'
import { Floor } from './components/Floor'
import { Register } from './components/Register'
import { ShiftReport } from './components/ShiftReport'
import { TicketRail } from './components/TicketRail'
import { Wire } from './components/Wire'
import { TICKET_TYPE, money } from './crew'
import { buildRun, latestRunId } from './desk'

type Toast = { kind: 'ok' | 'err'; text: string } | null

function WallClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  return <span className="clock">{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
}

function deskDate(iso: string | undefined): string {
  if (!iso) return '…'
  const d = new Date(`${iso}T12:00:00`)
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
}

export default function App() {
  const [tickets, setTickets] = useState<TicketCard[]>([])
  const [cash, setCash] = useState<CashView | null>(null)
  const [approvals, setApprovals] = useState<PendingApproval[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [detail, setDetail] = useState<TicketDetail | null>(null)
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null)
  const [online, setOnline] = useState<boolean | null>(null)
  const [tab, setTab] = useState<'wire' | 'report'>('wire')
  const [toast, setToast] = useState<Toast>(null)
  const [justResolved, setJustResolved] = useState<Set<number>>(new Set())
  const [dropping, setDropping] = useState(false)
  const [resetArmed, setResetArmed] = useState(false)
  const [starting, setStarting] = useState(false)

  const selectedRef = useRef<number | null>(null)
  const prevTickets = useRef<TicketCard[]>([])
  selectedRef.current = selected

  const say = useCallback((t: Toast) => {
    setToast(t)
    if (t) setTimeout(() => setToast(cur => (cur === t ? null : cur)), 5200)
  }, [])

  const loadTicket = useCallback(async (id: number) => {
    const [ev, d] = await Promise.all([api.events({ ticket_id: id }), api.ticket(id)])
    if (selectedRef.current !== id) return
    setEvents(ev.events)
    setDetail(d)
  }, [])

  const refresh = useCallback(async () => {
    try {
      const [t, c, a] = await Promise.all([api.tickets(), api.cash(), api.approvals()])
      setOnline(true)
      // Stamp animation for tickets that just flipped to resolved, and jump to the report
      const before = new Map(prevTickets.current.map(x => [x.ticket_id, x]))
      const flipped = t.filter(x => x.state === 'resolved' && before.get(x.ticket_id)?.state === 'open').map(x => x.ticket_id)
      if (flipped.length) {
        setJustResolved(new Set(flipped))
        setTimeout(() => setJustResolved(new Set()), 1600)
      }
      const finished = t.filter(x => !x.running && before.get(x.ticket_id)?.running)
      if (finished.some(x => x.ticket_id === selectedRef.current)) setTab('report')
      for (const x of finished) {
        say({ kind: 'ok', text: `Ticket #${x.ticket_id}: the team is done. ${x.state === 'resolved' ? 'Marked resolved.' : 'A payment needs your signature.'}` })
      }
      prevTickets.current = t
      setTickets(t)
      setCash(c)
      setApprovals(a)
      setSelected(cur => cur ?? t[0]?.ticket_id ?? null)
      const sel = selectedRef.current ?? t[0]?.ticket_id
      if (sel != null) await loadTicket(sel)
    } catch {
      setOnline(false)
    }
  }, [loadTicket, say])

  const anyRunning = starting || tickets.some(t => t.running)

  // Poll fast while the team is working, slowly otherwise.
  useEffect(() => {
    refresh()
    const t = setInterval(refresh, anyRunning ? 1500 : 7000)
    return () => clearInterval(t)
  }, [refresh, anyRunning])

  // Load the selected ticket's file and latest run right away when you pick it.
  useEffect(() => {
    if (selected == null) return
    setEvents([])
    setDetail(null)
    loadTicket(selected).catch(() => setOnline(false))
  }, [selected, loadTicket])

  const run = useMemo(() => buildRun(events, latestRunId(events)), [events])

  // Once a run started here finishes, fetch its stats (tokens, hand-offs) for the report.
  useEffect(() => {
    if (run.finished && runStatus && runStatus.team_run_id === run.runId && runStatus.state === 'running') {
      api.runStatus(runStatus.team_run_id).then(setRunStatus).catch(() => {})
    }
  }, [run.finished, run.runId, runStatus])

  async function startRun(id: number) {
    setStarting(true)
    try {
      const rs = await api.run(id)
      setRunStatus(rs)
      setSelected(id)
      setTab('wire')
      say({ kind: 'ok', text: `Ticket #${id} handed to the Boss. Watch the floor.` })
      await refresh()
    } catch (e) {
      say({ kind: 'err', text: (e as Error).message })
    } finally {
      setStarting(false)
    }
  }

  async function approve(a: PendingApproval, name: string) {
    try {
      const r = await api.approve({
        pay_kind: a.pay_kind, pay_ref_id: a.pay_ref_id, amount: a.amount, approved_by: name, ticket_id: a.ticket_id,
      })
      setDropping(true)
      setTimeout(() => setDropping(false), 1800)
      say({ kind: 'ok', text: `Paid ${money(r.payment.amount)} to ${a.payee}. Checking: ${money(r.balance_before)} → ${money(r.balance_after)}.` })
      await refresh()
    } catch (e) {
      say({ kind: 'err', text: (e as Error).message })
    }
  }

  async function reset() {
    if (!resetArmed) {
      setResetArmed(true)
      setTimeout(() => setResetArmed(false), 4000)
      return
    }
    setResetArmed(false)
    try {
      await api.reset()
      setRunStatus(null)
      setTab('wire')
      prevTickets.current = []
      say({ kind: 'ok', text: 'Fresh start: the database is back to its original values.' })
      await refresh()
    } catch (e) {
      say({ kind: 'err', text: (e as Error).message })
    }
  }

  const sel = tickets.find(t => t.ticket_id === selected) ?? null
  const label = sel ? `#${sel.ticket_id} · ${sel.subject} · ${TICKET_TYPE[sel.type]?.label ?? sel.type}` : null
  const notes = (detail?.ticket.notes ?? '').split('\n').filter(Boolean)

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="seal" aria-hidden>CC</span>
          <span className="brand-text">
            <span className="neon">Campus Customs</span>
            <span className="sub">Back office · Chapel Street</span>
          </span>
        </div>
        <div className="top-mid">
          <span className="chip-top">Desk date <b>{deskDate(cash?.as_of)}</b></span>
          <span className="chip-top">Now <WallClock /></span>
          <span className={`chip-top conn ${online ? 'on' : online === false ? 'off' : ''}`}>
            <i /> {online ? 'Backend connected' : online === false ? `Can't reach ${API_BASE}` : 'Connecting…'}
          </span>
        </div>
        <button className={`reset ${resetArmed ? 'armed' : ''}`} onClick={reset} disabled={anyRunning}>
          {resetArmed ? 'Click again to reset' : '↺ Fresh start'}
        </button>
      </header>

      <div className="grid">
        <TicketRail
          tickets={tickets}
          approvals={approvals}
          selected={selected}
          justResolved={justResolved}
          onSelect={id => { setSelected(id); setTab('wire') }}
          onRun={startRun}
          busy={starting}
        />

        <main className="center">
          <Floor run={run} ticketLabel={label} />
          <section className="logbook">
            <div className="tabs" role="tablist">
              <button role="tab" aria-selected={tab === 'wire'} onClick={() => setTab('wire')}>
                The wire <span className="n">{run.events.length}</span>
              </button>
              <button role="tab" aria-selected={tab === 'report'} onClick={() => setTab('report')}>
                Shift report {run.finished && <span className="n ready">ready</span>}
              </button>
            </div>
            {tab === 'wire'
              ? <Wire events={run.events} live={!run.finished} />
              : <ShiftReport run={run} report={detail?.last_report ?? null} runStatus={runStatus} requester={sel?.requester ?? null} payments={cash?.payments ?? []} />}
          </section>
        </main>

        <aside className="side">
          <Register cash={cash} dropping={dropping} />

          <section className="sign">
            <div className="side-head">
              <span className="kicker">Needs your signature</span>
              <span className={`count ${approvals.length ? 'hot' : ''}`}>{approvals.length}</span>
            </div>
            {approvals.length === 0 && (
              <div className="nothing">Nothing to sign. When an agent prepares a payment, the cheque lands here, and nothing moves until you sign it.</div>
            )}
            {approvals.map(a => (
              <Cheque key={`${a.pay_kind}${a.pay_ref_id}`} approval={a} balance={cash?.balance ?? null} onApprove={approve} />
            ))}
          </section>

          <section className="file">
            <div className="side-head"><span className="kicker">Ticket file</span>{sel && <span className="count">#{sel.ticket_id}</span>}</div>
            {!detail && <div className="nothing">Pick a ticket.</div>}
            {detail && (
              <>
                <dl className="file-facts">
                  <dt>From</dt><dd>{detail.ticket.requester}</dd>
                  {detail.ticket.sku && (<><dt>Item</dt><dd>{detail.ticket.sku} · {detail.ticket.size} · ×{detail.ticket.qty}</dd></>)}
                  {detail.ticket.invoice_id && (<><dt>Invoice</dt><dd>#{detail.ticket.invoice_id}</dd></>)}
                  {detail.ticket.lease_id && (<><dt>Lease</dt><dd>#{detail.ticket.lease_id}</dd></>)}
                  <dt>Status</dt><dd>{detail.ticket.status.replace('_', ' ')}</dd>
                </dl>
                <ol className="notes">
                  {notes.map((n, i) => {
                    const m = n.match(/^\[(\S+) ([^\]]+)\] (.*)$/)
                    return (
                      <li key={i} className={m ? '' : 'orig'}>
                        {m ? (<><span className="note-by">{m[2]}</span> {m[3]}</>) : (<><span className="note-by">Original request</span> {n}</>)}
                      </li>
                    )
                  })}
                </ol>
              </>
            )}
          </section>
        </aside>
      </div>

      {toast && <div className={`toast t-${toast.kind}`} role="status">{toast.text}</div>}
    </div>
  )
}
