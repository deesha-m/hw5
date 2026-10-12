# Campus Customs MCP Server

An MCP server, built with FastMCP, that gives the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service) and the vibe coder access to the shop's back-office database. Every agent gets its shop facts through these tools instead of querying SQLite directly, so all agents see the same facts and none of them invent prices, stock, balances or due dates.

## Database

- **Uses:** `data/campus_customs_new.db`, the working copy. Later problems update this file.
- **Never touches:** `data/campus_customs.db`, the original snapshot.
- **Override:** set the `CAMPUS_CUSTOMS_DB` environment variable to point at another file. The agent team's `--db` flag does this for test copies.
- **"Today"** is the database's `desk.date_today` (2026-08-31), not the computer clock. Tools report it as `as_of`.

## Tools

There are 14 tools: 12 read-only and 2 that write.

| Tool | Reads / writes | Main ticket | Returns |
|---|---|---|---|
| `list_open_tickets()` | reads `tickets` | all | Every ticket that isn't resolved, oldest first. |
| `list_tickets()` | reads `tickets` | all | Every ticket, open or resolved, with `is_open` (used by the dashboard API). |
| `get_ticket(ticket_id)` | reads `tickets`, `desk` | all | One ticket in full, with its SKU/size/qty, lease or invoice link. |
| `check_stock(sku, size?, qty?)` | reads `inventory`, `desk` | 101, 103 | Units per size, whether the request can be filled, and the shortfall. |
| `get_pricing(sku, qty?)` | reads `pricing`, `inventory` | 103 | Unit cost, list price, totals, and the cost floor. |
| `quote_discount(sku, qty, discount_pct)` | reads `pricing`, `inventory` | 103 | Discounted unit price and total, savings, margin, and `below_cost`. |
| `list_vendors()` | reads `vendors` | 101 | Vendors, what they supply, and lead days. |
| `get_invoice(invoice_id)` | reads `invoices`, `vendors`, `payments`, `tickets`, `desk` | 101 | Invoice, vendor, days overdue, payments made, linked tickets, and the earliest delivery if paid today. |
| `list_invoices(status?)` | reads `invoices`, `vendors`, `payments`, `tickets`, `desk` | 101 | All invoices (open by default), soonest due first. |
| `get_lease(lease_id)` | reads `leases`, `desk` | 102 | Landlord, rent, next due date, and days until due. |
| `get_cash_balance(account?)` | reads `cash_accounts`, `desk` | 101, 102 | The account balance, checked before any payment. |
| `list_payments()` | reads `payments` | 101, 102 | Every payment made, to prevent paying twice. |
| `record_payment(kind, ref_id, amount, approved_by, account?)` | **writes** `payments`, `cash_accounts`, `invoices` or `leases` | 101, 102 | Pays an invoice or rent in one transaction. |
| `update_ticket(ticket_id, status, note, author)` | **writes** `tickets` | all | Sets the status and appends a dated, signed note. Old notes are kept. |

## Rules enforced in the server's code

- **Unknown inputs:** an unknown ID, SKU, size or account returns an error listing the valid options instead of a guess.
- **`record_payment`** refuses unless:
  - `approved_by` is a named human (agent names and placeholders are rejected),
  - the amount equals the open invoice or the monthly rent on file exactly,
  - the invoice is still open, or the rent is due within 10 days (no double payment),
  - the account can cover it (no overdraft).

  Everything happens in one transaction: the payment is written, the balance is lowered, and the invoice is marked paid or the lease's due date moves forward a month.
- **`update_ticket`** only allows `open`, `in_progress`, `waiting` or `resolved`. It requires a note and an author, and only ever appends to the notes.
- **Labels for clients:** read tools are marked `readOnlyHint`, and write tools are marked as not read-only, so MCP clients can ask a human before calling them.

## Run

From the `homework/5` folder:

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python mcp_server/server.py
```

The server speaks MCP over stdio. The vibe coder starts it from `.mcp.json`, and the agent team (`backend/agents.py`) starts its own connection to it.
