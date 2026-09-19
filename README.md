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
| 5.8 | Chart of Accounts restructuring + real opening trial balance import | `models/res_company.py`, data in `data/import/` |
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

## Chart of Accounts, opening trial balance, Customers & Vendors, bank accounts

`models/res_company.py`'s `_combine001_run_import()` replaces the company's
Chart of Accounts and opening trial balance with the client's actual data
— extracted from `D:\Others\Combine Spinning\coa and opening trial.xlsx`
(Chart of Accounts sheet, a Delta ERP trial balance with levels, as on
15-Sep-2026) and `D:\Others\Combine Spinning\Customers and Vendors.xlsx`.
The cleaned data it imports from is bundled at `data/import/*.csv`
(generated once from those two workbooks, not re-read from them at
install/upgrade time).

**Runs on install AND on every module upgrade** — wired via a
non-`noupdate` `<function>` tag (`data/combine001_import_run.xml`), not
`post_init_hook`: `post_init_hook` only ever fires on a fresh install,
never on `-u`/Upgrade, which is why the data didn't show up after the
first deploy on a database where the module was already installed before
this feature existed. The whole thing is written to be safe to re-run
on every future upgrade too:

- Accounts, account groups, bank journals and Customers/Vendors are all
  **found-or-created by their natural key** (code / name) instead of
  blindly recreated, so re-running never produces duplicates.
- Until the opening balance is posted (see below), every run does a
  **full, clean rebuild**: any pre-existing journal entries for the
  company are cleared first (see step 1) so accounts/groups/opening
  balances always come out correct and consistent — no partial/stale
  leftovers, no "only some of it shows up."
- Opening balances are (re)computed via Odoo's native
  `opening_debit`/`opening_credit` fields — the same mechanism Odoo's own
  CSV-import UI uses — every time the pre-posted rebuild runs, right after
  the reset in step 1 clears whatever the previous run's lines were, so
  there's never a stale line for Odoo's own auto-balancing mechanism to
  collide with. (Setting these fields doesn't build the move
  synchronously — it queues a precommit callback — so the import forces
  an `env.cr.flush()` before posting, otherwise `account_opening_move_id`
  reads back empty.)
- Once the opening move has actually been **posted** (i.e. the business
  has gone live on this data), a later upgrade **skips the Chart of
  Accounts / opening balance / currency part entirely** rather than
  resetting and rewriting live financial data — logged as a warning.
  Customers, Vendors and bank journals still refresh normally either way.

**What it does, step by step:**

1. Unless the opening move is already posted (skip straight to step 6 if
   so — see above): **clears every existing journal entry** for the
   company, posted or draft (unposts first if needed). This is what
   actually fixes "only 2 lines show in the Trial Balance" and "still in
   USD" — both were caused by leftover entries from *before* this import
   ever completed correctly (e.g. Odoo's own fallback CoA auto-install,
   step 3, completing before this module's fix was in place, or ad hoc
   testing) sitting there blocking things: Odoo's Trial Balance/General
   Ledger/Balance Sheet only show *posted* entries by default, so with
   the real 1,007-account opening balance stuck in draft, only those
   stray entries were visible; and Odoo flatly refuses to change company
   currency while *any* `account.move.line` exists at all (posted or
   draft) — including this import's own opening balance from a prior run,
   which is why the currency fix kept silently failing after the very
   first attempt.
2. Sets the company currency to **PKR**, now that step 1 has cleared
   anything that would block it (activates the PKR currency record if
   needed).
3. Cancels Odoo's own fallback "auto-install a generic Chart of Accounts"
   behaviour, which would otherwise create a *second*, competing default
   CoA and journals for any company with no localization chosen (see the
   big comment on `_combine001_cancel_generic_coa_auto_install` — this was
   the one genuinely surprising Odoo 19 internal to work around).
4. Creates a `Miscellaneous Operations` (general), `Customer Invoices`
   (sale) and `Vendor Bills` (purchase) journal if the company doesn't
   already have one of each — needed for day-to-day invoicing and for the
   opening move itself.
5. Imports **126 account groups** (Level 1–3 of the source CoA) and
   **1,007 accounts** (Level 4 posting accounts) with their opening
   balances, then **posts the opening move** — real opening balances (a
   ~21.4 billion Rs trial balance) would ideally be reviewed by a Finance
   Manager before posting, but it's posted automatically here so the data
   actually shows up in every standard report; any residual rounding is
   auto-balanced by Odoo against the equity "Undistributed Profits"
   account. Once posted, it's protected from every future rebuild (see
   above) — a correction after that point should be a proper reviewed
   accounting adjustment, not another module upgrade silently rewriting
   it.
6. **Debtors/Creditors control accounts (BRD COA-001/002/003):** instead
   of importing the source's 331 individual vendor-named and 33
   individual customer-named GL leaf accounts, this creates one **control
   account** per named sub-group instead (e.g. "CREDITORS-RAW MATERIAL",
   "DEBTORS - EXPORT"), each carrying that sub-group's own rolled-up
   opening balance from the source trial balance — mathematically
   identical to the sum of the individual accounts it replaces (verified:
   the two differ by Rs 1 out of ~21.4 billion, pure floating-point
   rounding in the source spreadsheet). Customer/vendor-level detail is
   tracked the Odoo-native way instead: via `partner_id` on the journal
   item (Partner Ledger), not a separate GL account per party. Any
   pre-existing account whose code is not part of this import gets
   archived (not deleted — other configs may reference it).
7. **Bank/cash accounts and journals:** every one of the ~30 real, named
   accounts under "CASH AND BANK BALANCE" is imported as its own GL
   account (like any other posting account, step 5) *and* gets its own
   `account.journal` (type `bank` or `cash`, per whether its code is under
   `3.14.01.*` "Cash in Hand"), linked via `default_account_id`. The one
   with the single largest opening debit balance is marked as the default
   (lowest `sequence`, so it's the one every journal/payment picker shows
   first) — currently "MEEZAN BANK 0204-0100906298".
8. Imports the **341 customers** and **346 vendors** from the Customers
   and Vendors workbook as `res.partner` Contacts (`customer_rank`/
   `supplier_rank` set), each with `property_account_receivable_id` /
   `property_account_payable_id` pointing at the correct control account
   — determined from that party's *original* code prefix in the source
   workbook (e.g. a vendor coded under `2.07.01.xxxx` gets the
   "CREDITORS-RAW MATERIAL" control account), even though the new account
   codes themselves ignore those old numbers, per the ask. A party whose
   original group has no named control account (most customers — see
   below) falls back to one general control account each: `3.09.01`
   "TRADE DEBTORS - LOCAL SALES (GENERAL)" for customers, the existing
   `2.07.09` "CREDITORS - OTHERS" for vendors. Runs every time regardless
   of whether the opening move is posted, so party master data always
   stays current.

**Note on data completeness:** the source CoA workbook explicitly excludes
"dormant" accounts (both Debit and Credit closing balance in {0, 1, 2} Rs)
from the *balance* extract — see its Notes sheet. Most customers (308 of
341) fall under debtor sub-groups that got excluded this way (their
balances had fully netted out by the snapshot date), which is why they
route to the one general control account above rather than a named
sub-group; only 15 of 346 vendors are in the equivalent situation. This
does **not** mean those parties are missing — the Customers and Vendors
workbook is unfiltered, so all of them are imported as Contacts either
way; only the not-currently-meaningful GL sub-group distinction is
collapsed for them.

**Not done automatically, by design** (would require guessing at real
business specifics this data doesn't contain): rewiring the *other*
company-level default-account settings (cash-difference accounts,
early-payment-discount accounts, product category default income/expense
accounts, tax repartition line accounts, fiscal positions) that a prior
chart-of-accounts template may have set to now-archived accounts, and
deciding whether the auto-picked default bank journal (largest opening
balance) is actually the one that should be used going forward. Review
Accounting > Configuration before go-live.

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

## Install / Upgrade

Addon lives under `~/odoo/custom/` (symlinked as `combine001` ->
`combine001_odoo/combine001`) on the WSL Odoo dev instance, addons path
already includes `~/odoo/custom`. Fresh install:

```
odoo-bin -c <conf> -d <db> -i combine001 --stop-after-init
```

Upgrade an already-installed database to pick up code/data changes
(including a re-run of the CoA/opening-balance/Customers&Vendors import,
per the safety rules described above):

```
odoo-bin -c <conf> -d <db> -u combine001 --stop-after-init
```

On Odoo.sh or any web-based install, the equivalent is: push to the
tracked branch, then in that database's backend go to **Apps**, clear the
"Apps" filter, search **Combine001**, and click **Upgrade** (not just
confirm it's installed — Upgrade is what re-runs the import).
