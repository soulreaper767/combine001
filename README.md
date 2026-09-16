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
