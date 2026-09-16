# Combine001

Odoo 19 custom app implementing the "Odoo ERP Enhancements v1.0" BRD
(Sibyl Technologies, for Combine Spinning, 2026-09-16).

## Layout

- `combine001/` — the Odoo module (installable, `application: True`). All
  configuration, security groups, views and menus load automatically when
  the module is installed — no manual setup steps required.

## What it implements

| BRD Section | Feature | Where |
|---|---|---|
| 5.1 | Sales Order price-change approval workflow + audit trail | `models/sale_order.py` |
| 5.1.2 / 5.2 | Quotation qty ceiling, item-wise & customer-wise qty limits | `models/sale_order.py`, `models/product_template.py`, `models/customer_item_limit.py` |
| 5.3 | Cumulative delivery quantity validation | `models/stock_move.py` |
| 5.4 | Cumulative invoice quantity validation | `models/account_move.py` |
| 5.5 | Sales Tax Template | native Odoo `account.tax` — no custom code needed |
| 5.6 | Additional charges (freight/transport/handling/service) | `models/charge_type.py`, `wizard/add_charge_wizard.py` |
| 5.7 | Commission Agent + automatic commission calc on invoice | `models/commission_agent.py`, `models/commission_line.py`, `models/account_move.py` |
| 5.8 | Chart of Accounts restructuring | native `account.move.line.partner_id` (Partner Ledger) — no customer-level GL accounts created by this module |
| 7 | Separate Tax Ledger + controlled manual adjustment | `views/tax_ledger_views.xml`, `models/tax_adjustment.py` |
| 10 | Security groups (Tax Officer, Auditor) + audit trail via chatter | `security/combine001_security.xml` |
| 3.1 | One demo user per defined role, pre-assigned to the right groups | `data/combine001_users_data.xml` |

## Demo users (BRD Section 3.1)

One user per role is created on install, already in the group(s) from the
BRD's Section 3.2 access matrix:

| Role | Login |
|---|---|
| Sales User | `sales.user@combine001.local` |
| Sales Manager | `sales.manager@combine001.local` |
| Warehouse / Inventory User | `warehouse.user@combine001.local` |
| Accountant | `accountant@combine001.local` |
| Finance Manager / Controller | `finance.manager@combine001.local` |
| Tax Officer | `tax.officer@combine001.local` |
| System Administrator | `system.admin@combine001.local` |
| Auditor | `auditor@combine001.local` (read-only on Sales Orders, Invoices,
  Payments, Deliveries and every Combine001 model — see `views/audit_views.xml`) |

**No password is set** — these are placeholder accounts committed to a
public git repo, and a hardcoded password there would be a credential
leak. After install, a System Administrator sets each one's password
locally via *Settings > Users & Companies > Users > (user) > Action >
Change Password*, or triggers *Send Password Reset Instructions* if
outgoing mail is configured. They're meant as a starting point for
setup/UAT — rename, reassign, or deactivate them and create real named
accounts once the client's staff list is confirmed.

Each user's `group_ids` lists the full closure of groups for that role
explicitly (e.g. Sales Manager includes the Salesman group, Finance
Manager includes the Accountant group) rather than relying on a group's
`implied_ids` to cascade automatically: testing on this Odoo 19 build
showed `implied_ids` does not propagate to a user created via a plain
`(6, 0, [...])` write on `group_ids` in XML data — see the comment in
`data/combine001_users_data.xml`.

## Assumptions made for the BRD's open items (Section 12)

The BRD explicitly leaves six points open for client sign-off. This module
ships a working default for each so the app is usable end-to-end now;
change these in code once the client confirms:

1. **Quantity hierarchy precedence** — all applicable limits (quotation
   qty, item limit, customer+item limit) are enforced independently; the
   most restrictive one blocks first.
2. **Price-override approval** — flat rule: *any* price change away from
   the quoted price on a draft/sent order routes to a Sales Manager.
3. **Invoicing policy** — order-based: invoice quantity is validated
   against the Sales Order quantity (not delivered quantity).
4. **Commission base** — configurable per Commission Agent / Sales Order
   (`sales_value` / `product_value` / `quantity` / `net_sales_value`);
   defaults to Sales Value. `product_value` and `net_sales_value` are
   currently computed the same as `sales_value` (invoice line subtotal).
5. **Customer accounting dimension** — uses Odoo's native `partner_id` on
   journal items (Partner Ledger / Aged Receivable reports already give
   customer-wise detail); no new dimension model was added.
6. **Tax Ledger adjustment approval** — single level: Finance Manager
   approves. Approval only marks the request Approved — it does not
   auto-post a journal entry, since the actual GL accounts to use are
   part of the still-open Chart of Accounts restructuring (COA-003); the
   Accountant posts the entry manually referencing the approved record.

## Install

Addon lives under `~/odoo/custom/` (symlinked as `combine001` ->
`combine001_odoo/combine001`) on the WSL Odoo dev instance, addons path
already includes `~/odoo/custom`. Install/update via:

```
odoo-bin -c <conf> -d <db> -i combine001 --stop-after-init
```
