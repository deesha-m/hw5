import type { AgentEvent, Role } from './api'

// Each agent has its own color, glyph and voice so you can tell who's talking at a glance.
export interface CrewMember {
  role: Role
  name: string
  title: string
  glyph: string
  color: string
  voice: string // how their bubble reads while they work
  idle: string
}

export const CREW: Record<Role, CrewMember> = {
  boss: {
    role: 'boss', name: 'Boss', title: 'Store manager', glyph: '★', color: '#00356b',
    voice: 'Calling the shots', idle: 'Waiting for a ticket',
  },
  inventory: {
    role: 'inventory', name: 'Inventory', title: 'Stockroom', glyph: '▦', color: '#93703e',
    voice: 'Counting the shelf', idle: 'Stockroom quiet',
  },
  accounting: {
    role: 'accounting', name: 'Accounting', title: 'Money & invoices', glyph: '$', color: '#2f7d5b',
    voice: 'Running the numbers', idle: 'Ledger closed',
  },
  facilities: {
    role: 'facilities', name: 'Facilities', title: 'Lease & landlord', glyph: '⌂', color: '#8c3b2c',
    voice: 'Checking the lease', idle: 'Keys on the hook',
  },
  customer_service: {
    role: 'customer_service', name: 'Customer Service', title: 'Voice of the shop', glyph: '✉', color: '#286dc0',
    voice: 'Writing to the customer', idle: 'Inbox clear',
  },
}

export const ROLES: Role[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export function crew(role: string): CrewMember {
  return CREW[role as Role] ?? { ...CREW.boss, role: role as Role, name: role, glyph: '•', color: '#857e72' }
}

// Plain-English verbs for the MCP tools, used in speech bubbles and the wire.
const TOOL_VERBS: Record<string, string> = {
  get_ticket: 'Reading the ticket',
  list_open_tickets: 'Scanning the open queue',
  list_tickets: 'Scanning tickets',
  check_stock: 'Checking the shelf',
  get_pricing: 'Looking up the price tag',
  quote_discount: 'Pricing a discount',
  list_vendors: 'Flipping through vendors',
  get_invoice: 'Pulling the invoice',
  list_invoices: 'Reviewing open bills',
  get_lease: 'Pulling the lease file',
  get_cash_balance: 'Checking the bank balance',
  list_payments: 'Checking what’s been paid',
  record_payment: 'Recording a payment',
  update_ticket: 'Writing a note on the ticket',
  delegate: 'Handing off',
  final_result: 'Writing up the report',
}

export function toolVerb(tool: string): string {
  return TOOL_VERBS[tool] ?? tool.replaceAll('_', ' ')
}

export function shortArgs(args: ToolCall['args']): string {
  if (typeof args === 'string') return args
  return Object.entries(args)
    .filter(([k]) => !['note', 'author', 'task'].includes(k))
    .map(([, v]) => String(v))
    .join(', ')
}
type ToolCall = AgentEvent['tools_called'][number]

export const STATUS_LABEL: Record<string, string> = {
  done: 'Done',
  waiting_on_approval: 'Needs approval',
  blocked: 'Waiting on someone',
  escalated: 'Escalated',
  refused: 'Refused',
}

export const TICKET_TYPE: Record<string, { label: string; icon: string }> = {
  customer_order: { label: 'Customer order', icon: '👕' },
  rent_notice: { label: 'Rent notice', icon: '🏠' },
  price_override: { label: 'Price override', icon: '🏷️' },
}

export function money(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

// For the cheque: 840 -> "Eight hundred forty and 00/100"
const ONES = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
  'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
const TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
function under1000(n: number): string {
  const h = Math.floor(n / 100)
  const rest = n % 100
  const parts: string[] = []
  if (h) parts.push(`${ONES[h]} hundred`)
  if (rest >= 20) parts.push(TENS[Math.floor(rest / 10)] + (rest % 10 ? `-${ONES[rest % 10]}` : ''))
  else if (rest) parts.push(ONES[rest])
  return parts.join(' ')
}
export function amountInWords(amount: number): string {
  const dollars = Math.floor(amount)
  const cents = Math.round((amount - dollars) * 100)
  const th = Math.floor(dollars / 1000)
  const rest = dollars % 1000
  let words = [th ? `${under1000(th)} thousand` : '', rest ? under1000(rest) : ''].filter(Boolean).join(' ')
  if (!words) words = 'zero'
  return `${words[0].toUpperCase()}${words.slice(1)} and ${String(cents).padStart(2, '0')}/100`
}
