import { useState } from 'react'
import type { PendingApproval } from '../api'
import { amountInWords, crew, money } from '../crew'

interface Props {
  approval: PendingApproval
  balance: number | null
  onApprove: (a: PendingApproval, name: string) => Promise<void>
}

/** A payment the agents prepared, laid out as a cheque the human signs. */
export function Cheque({ approval, balance, onApprove }: Props) {
  const [name, setName] = useState(() => localStorage.getItem('desk-signer') ?? '')
  const [busy, setBusy] = useState(false)
  const after = balance === null ? null : balance - approval.amount
  const valid = name.trim().length >= 3

  async function sign() {
    if (!valid || busy) return
    setBusy(true)
    localStorage.setItem('desk-signer', name.trim())
    try {
      await onApprove(approval, name.trim())
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="cheque">
      <div className="cheque-top">
        <span className="bank">CAMPUS CUSTOMS · CHECKING</span>
        <span className="cheque-no">Ticket #{approval.ticket_id ?? '—'}</span>
      </div>
      <div className="payto">
        <span className="lbl">Pay to the order of</span>
        <span className="payee">{approval.payee}</span>
        <span className="amount-box">{money(approval.amount)}</span>
      </div>
      <div className="words">{amountInWords(approval.amount)} dollars</div>
      <div className="memo">
        <span className="lbl">Memo</span> {approval.pay_kind} {approval.pay_ref_id} · prepared by {crew(approval.requested_by).name}
      </div>
      <p className="why">{approval.reason}</p>
      {after !== null && (
        <div className={`after ${after < 500 ? 'warn' : ''}`}>
          Checking after: <b>{money(after)}</b>{after < 500 && ' · below the $500 cushion'}
        </div>
      )}
      <div className="sign-row">
        <label>
          <span className="lbl">Your signature</span>
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sign()}
            placeholder="Type your full name"
            aria-label="Your full name"
          />
        </label>
        <button className="sign-btn" disabled={!valid || busy} onClick={sign}>
          {busy ? 'Paying…' : `Approve & pay ${money(approval.amount)}`}
        </button>
      </div>
      <div className="fineprint">Agents only prepare payments. Your signature is what moves the money.</div>
    </div>
  )
}
