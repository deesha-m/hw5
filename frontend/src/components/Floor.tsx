import type { Role } from '../api'
import { CREW, ROLES, STATUS_LABEL, toolVerb } from '../crew'
import type { RunView } from '../desk'

// Where each desk sits on the floor (percent of the floor box). The Boss is in the middle.
const SEAT: Record<Role, { x: number; y: number }> = {
  boss: { x: 50, y: 50 },
  inventory: { x: 17, y: 21 },
  accounting: { x: 83, y: 21 },
  facilities: { x: 17, y: 79 },
  customer_service: { x: 83, y: 79 },
}

const PAIRS: [Role, Role][] = ROLES.flatMap((a, i) => ROLES.slice(i + 1).map(b => [a, b] as [Role, Role]))

export function Floor({ run, ticketLabel }: { run: RunView; ticketLabel: string | null }) {
  const live = run.runId && !run.finished
  return (
    <section className="floor" aria-label="Agent floor">
      <div className="floor-head">
        <span className="kicker">The floor</span>
        <span className="floor-title">
          {ticketLabel ? ticketLabel : 'No ticket selected'}
          {live && <span className="live-dot">LIVE</span>}
          {run.finished && <span className="done-dot">SHIFT DONE</span>}
        </span>
      </div>

      <div className="floor-map">
        <svg className="wires" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
          {PAIRS.map(([a, b]) => (
            <line key={`${a}${b}`} x1={SEAT[a].x} y1={SEAT[a].y} x2={SEAT[b].x} y2={SEAT[b].y} className="wire-faint" />
          ))}
          {run.edges.map(e => (
            <line
              key={`${e.from}>${e.to}`}
              x1={SEAT[e.from].x} y1={SEAT[e.from].y} x2={SEAT[e.to].x} y2={SEAT[e.to].y}
              className={`wire-${e.state}`}
              style={{ stroke: CREW[e.from].color }}
            />
          ))}
        </svg>

        {ROLES.map(role => {
          const a = run.agents[role]
          const c = CREW[role]
          const seat = SEAT[role]
          const from = a.delegatedBy ? CREW[a.delegatedBy as Role]?.name : null
          return (
            <div
              key={role}
              className={`desk desk-${role} is-${a.status}`}
              style={{ left: `${seat.x}%`, top: `${seat.y}%`, ['--c' as string]: c.color }}
            >
              <div className="desk-id">
                <span className="avatar" aria-hidden>{c.glyph}</span>
                <div>
                  <div className="desk-name">{c.name}</div>
                  <div className="desk-title">{c.title}</div>
                </div>
                <span className={`lamp lamp-${a.status}`} title={a.status} />
              </div>
              <div className="bubble">
                {a.status === 'working' && a.currentTools.length > 0 && (
                  <div className="doing">
                    {[...new Set(a.currentTools)].map(t => {
                      const n = a.currentTools.filter(x => x === t).length
                      return toolVerb(t) + (n > 1 ? ` ×${n}` : '')
                    }).join(' · ')}
                  </div>
                )}
                <p>{a.line}</p>
              </div>
              <div className="desk-foot">
                {a.status === 'idle' && <span className="muted">{run.runId ? 'Not on this ticket' : 'Ready'}</span>}
                {a.status !== 'idle' && (
                  <>
                    {from && <span className="from">via {from}</span>}
                    <span className="steps">{a.steps} step{a.steps === 1 ? '' : 's'}</span>
                    {a.reportStatus && <span className={`pill p-${a.reportStatus}`}>{STATUS_LABEL[a.reportStatus] ?? a.reportStatus}</span>}
                    {a.blocked.length > 0 && <span className="pill p-blocked" title={a.blocked.join('\n')}>guardrail ×{a.blocked.length}</span>}
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
