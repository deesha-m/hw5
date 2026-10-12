import { useEffect, useRef, useState } from 'react'
import type { CashView } from '../api'
import { money } from '../crew'

/** Animates a number from its old value to the new one, like a register drawer counting. */
function useCounter(target: number | null, ms = 1400): number | null {
  const [shown, setShown] = useState(target)
  const from = useRef(target)
  useEffect(() => {
    if (target === null) return
    const start = from.current ?? target
    if (start === target) { setShown(target); return }
    const t0 = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / ms)
      const ease = 1 - Math.pow(1 - p, 3)
      setShown(start + (target - start) * ease)
      if (p < 1) raf = requestAnimationFrame(tick)
      else from.current = target
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return shown
}

export function Register({ cash, dropping }: { cash: CashView | null; dropping: boolean }) {
  const shown = useCounter(cash?.balance ?? null)
  return (
    <section className={`register ${cash?.low_cash ? 'low' : ''} ${dropping ? 'dropping' : ''}`} aria-label="Checking balance">
      <div className="register-head">
        <span className="kicker">Checking</span>
        <span className={`cushion ${cash?.low_cash ? 'warn' : ''}`}>{cash?.low_cash ? 'Below $500 cushion' : 'Cushion OK'}</span>
      </div>
      <div className="led" aria-live="polite">{shown === null ? '—' : money(shown)}</div>
      <div className="register-sub">as of desk date {cash?.as_of ?? '…'}</div>
      <div className="receipt">
        <div className="receipt-title">Paid out</div>
        {cash && cash.payments.length === 0 && <div className="receipt-empty">Nothing paid yet today.</div>}
        {cash?.payments.map(p => (
          <div key={p.payment_id} className="receipt-row">
            <span>#{p.payment_id} {p.kind} {p.ref_id}</span>
            <span className="amt">−{money(p.amount)}</span>
            <span className="by">signed {p.approved_by}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
