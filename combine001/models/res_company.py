import csv
import logging
import os
from datetime import date

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_IMPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'import')

_GENERAL_DEBTOR_CODE = '3.09.01'
_GENERAL_CREDITOR_FALLBACK_CODE = '2.07.09'

# The trial balance this data was extracted from is dated 15-Sep-2026.
# Odoo dates the opening move as account_opening_date minus one day, so
# account_opening_date is set to the day after.
_OPENING_DATE = date(2026, 9, 16)

_CASH_BANK_PREFIX = '3.14.'
_CASH_SUBPREFIX = '3.14.01.'


def _read_csv(filename):
    path = os.path.join(_IMPORT_DIR, filename)
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def _combine001_run_import(self):
        """Import Combine Spinning's real Chart of Accounts, opening trial
        balance, Customers/Vendors and bank accounts.

        Runs on both module install AND every module upgrade (wired via a
        non-noupdate <function> tag in data/combine001_import_run.xml,
        not via post_init_hook - post_init_hook only fires on install,
        never on upgrade, which is why this didn't show up after the
        first deploy). Safe to re-run: accounts/groups/journals/partners
        are found-or-created by their natural key (code / name) instead of
        blindly recreated.

        Once the opening balance has actually been posted (i.e. the
        business has gone live on this data), a later upgrade skips the
        whole Chart of Accounts / opening balance / currency part
        entirely rather than rewriting live financial data - only
        Customers/Vendors/bank journals keep refreshing after that point.
        Until then, every run does a full, clean rebuild: any existing
        journal entries (including stray/test ones from before this
        import ever completed correctly, which also blocks changing the
        company currency) are cleared first, so this is always safe to
        re-run right up until go-live.
        """
        company = self.env.company
        _logger.info("Combine001: running import for company %s", company.name)

        self._combine001_cancel_generic_coa_auto_install()

        if company.opening_move_posted():
            _logger.warning(
                "Combine001: opening move is already posted - skipping the "
                "Chart of Accounts / opening balance / currency (re-)import "
                "to avoid rewriting live data. Customers/Vendors/bank "
                "journals are still refreshed."
            )
            account_by_code = {a.code: a.id for a in self.env['account.account'].search([])}
        else:
            self._combine001_reset_accounting(company)
            self._combine001_set_currency(company)
            self._combine001_ensure_baseline_journals(company)
            self._combine001_import_account_groups(company)
            account_by_code = self._combine001_import_accounts(company)
            self._combine001_archive_stale_accounts(company, set(account_by_code))
            if not company.account_opening_date:
                company.account_opening_date = _OPENING_DATE
            if not company.chart_template:
                company.chart_template = 'generic_coa'
            self._combine001_post_opening_move(company)

        self._combine001_import_bank_journals(company, account_by_code)
        self._combine001_import_partners(
            company, 'customers.csv', 'receivable_account_code', account_by_code,
            customer_rank=1, supplier_rank=0, property_field='property_account_receivable_id',
        )
        self._combine001_import_partners(
            company, 'vendors.csv', 'payable_account_code', account_by_code,
            customer_rank=0, supplier_rank=1, property_field='property_account_payable_id',
        )

        _logger.info("Combine001: import complete - %s accounts on record.", len(account_by_code))

    # -- reset ------------------------------------------------------------

    def _combine001_reset_accounting(self, company):
        """Clear every existing account.move (posted or draft) for this
        company before rebuilding the opening balance from scratch.

        Only ever called while the opening move is NOT posted (see
        caller), so this can never touch real, reviewed go-live data - it
        only clears leftover/test entries from before a correct import
        ever completed (Odoo's own fallback CoA auto-install runs the
        moment the 'account' module is first installed, before this
        module's own post_init/upgrade logic gets a chance to run, and
        may have posted its own default setup; anything created while
        testing before this import was wired up correctly counts too).
        Those stray entries are also *exactly* what blocks the company
        currency change below (Odoo's `_existing_accounting()` check
        triggers on any account.move.line at all, posted or draft -
        including this module's own opening balance from a prior run)."""
        Move = self.env['account.move'].with_context(active_test=False)
        moves = Move.search([('company_id', 'child_of', company.id)])
        if not moves:
            return
        try:
            posted = moves.filtered(lambda m: m.state == 'posted')
            if posted:
                posted.button_draft()
            moves.unlink()
        except UserError as exc:
            _logger.warning(
                "Combine001: could not clear %s pre-existing journal entries "
                "(%s) - they may be locked/hashed. Leaving them in place; "
                "this may also block the currency change below.",
                len(moves), exc,
            )
            return
        company.account_opening_move_id = False
        _logger.warning(
            "Combine001: cleared %s pre-existing journal entries before "
            "rebuilding the Chart of Accounts and opening balance from "
            "scratch.", len(moves),
        )

    # -- currency -------------------------------------------------------

    def _combine001_set_currency(self, company):
        """The trial balance is entirely in PKR."""
        if company.currency_id.name == 'PKR':
            return
        pkr = self.env['res.currency'].with_context(active_test=False).search([('name', '=', 'PKR')], limit=1)
        if not pkr:
            _logger.warning("Combine001: no PKR currency record found on this database - skipping currency change.")
            return
        if not pkr.active:
            pkr.active = True
        try:
            company.currency_id = pkr.id
            _logger.info("Combine001: company currency set to PKR.")
        except UserError:
            _logger.warning(
                "Combine001: could not change company currency to PKR - accounting entries already "
                "exist (Odoo forbids changing currency once journal items are posted)."
            )

    # -- disable Odoo's own fallback CoA auto-install --------------------

    def _combine001_cancel_generic_coa_auto_install(self):
        """Installing the 'account' module (a combine001 dependency)
        unconditionally queues a one-shot callback on the registry that
        auto-installs Odoo's fallback 'Generic Chart of Accounts' template
        (with its own journals/accounts) the moment the *whole* module
        graph finishes loading - regardless of what this method does
        afterwards. That callback is queued while chart_template is still
        unset, so setting chart_template later does not stop it; the only
        way to stop it is to remove the queued callback itself, which is
        exactly what should happen since this module replaces the CoA
        with the client's own."""
        registry = self.env.registry
        if hasattr(registry, '_auto_install_template'):
            del registry._auto_install_template

    # -- journals ---------------------------------------------------------

    def _combine001_ensure_baseline_journals(self, company):
        """A company with no chart template loaded has no journals at all.
        The opening move needs an existing 'general' type journal; regular
        Sales Orders / Vendor Bills need a 'sale' / 'purchase' journal.
        Neither needs a specific default account (they fall back to
        product-category accounts)."""
        Journal = self.env['account.journal']
        for jtype, code, name in (
            ('general', 'MISC', 'Miscellaneous Operations'),
            ('sale', 'INV', 'Customer Invoices'),
            ('purchase', 'BILL', 'Vendor Bills'),
        ):
            if not Journal.search([('company_id', '=', company.id), ('type', '=', jtype)], limit=1):
                Journal.create({'name': name, 'code': code, 'type': jtype, 'company_id': company.id})

    def _combine001_import_bank_journals(self, company, account_by_code):
        """One bank/cash journal per bank/cash account in the imported CoA
        (~30 real named accounts under 'CASH AND BANK BALANCE'), each
        linked to its matching GL account. The one with the largest
        opening debit balance is set as the default (lowest sequence, so
        it's the one shown first in every journal/payment picker)."""
        rows = [r for r in _read_csv('accounts.csv') if r['code'].startswith(_CASH_BANK_PREFIX)]
        if not rows:
            return

        Journal = self.env['account.journal']
        candidates = []
        for row in rows:
            account_id = account_by_code.get(row['code'])
            if not account_id:
                continue
            jtype = 'cash' if row['code'].startswith(_CASH_SUBPREFIX) else 'bank'
            code = ('C' if jtype == 'cash' else 'B') + row['code'].rsplit('.', 1)[-1][-4:]
            journal = Journal.search([('company_id', '=', company.id), ('default_account_id', '=', account_id)], limit=1)
            if not journal:
                journal = Journal.search([('company_id', '=', company.id), ('code', '=', code)], limit=1)
            vals = {
                'name': row['name'],
                'code': code,
                'type': jtype,
                'company_id': company.id,
                'default_account_id': account_id,
            }
            if journal:
                journal.write(vals)
            else:
                journal = Journal.create(vals)
            candidates.append((float(row['opening_debit'] or 0), journal))

        if candidates:
            candidates.sort(key=lambda c: c[0], reverse=True)
            default_journal = candidates[0][1]
            default_journal.sequence = 1
            for i, (_, journal) in enumerate(candidates[1:], start=2):
                journal.sequence = i
            _logger.info("Combine001: %s bank/cash journals imported, default is '%s'.",
                         len(candidates), default_journal.name)

    # -- chart of accounts ------------------------------------------------

    def _combine001_import_account_groups(self, company):
        rows = _read_csv('account_groups.csv')
        Group = self.env['account.group']
        existing = {g.code_prefix_start: g for g in Group.search([('company_id', '=', company.root_id.id)])}
        to_create = []
        for row in rows:
            vals = {
                'name': row['name'],
                'code_prefix_start': row['code'],
                'code_prefix_end': row['code'],
                'company_id': company.root_id.id,
            }
            found = existing.get(row['code'])
            if found:
                found.write(vals)
            else:
                to_create.append(vals)
        if to_create:
            Group.create(to_create)

    def _combine001_import_accounts(self, company):
        rows = _read_csv('accounts.csv')
        Account = self.env['account.account']
        existing = {a.code: a for a in Account.with_context(active_test=False).search([('company_ids', 'in', company.id)])}

        to_create = []
        account_by_code = {}
        for row in rows:
            account_type = row['account_type']
            vals = {
                'code': row['code'],
                'name': row['name'],
                'account_type': account_type,
                'active': True,
                'company_ids': [(6, 0, [company.id])],
            }
            if account_type in ('asset_receivable', 'liability_payable'):
                vals['reconcile'] = True

            found = existing.get(row['code'])
            if found:
                found.write(vals)
                account_by_code[row['code']] = found.id
            else:
                to_create.append(vals)

        if to_create:
            created = Account.create(to_create)
            for account in created:
                account_by_code[account.code] = account.id

        # Safe to (re)apply opening balances to every account here: this
        # method only ever runs right after _combine001_reset_accounting
        # has wiped all pre-existing journal items for the company, so
        # there is no existing opening-move line for Odoo's own
        # auto-balancing mechanism to collide with.
        by_code = {row['code']: row for row in rows}
        for code, account_id in account_by_code.items():
            row = by_code[code]
            debit = float(row['opening_debit'] or 0)
            credit = float(row['opening_credit'] or 0)
            if debit or credit:
                account = Account.browse(account_id)
                account.opening_debit = debit
                account.opening_credit = credit

        return account_by_code

    def _combine001_post_opening_move(self, company):
        """Post the freshly-rebuilt opening balance so it actually shows
        up in the Trial Balance / General Ledger / Balance Sheet, which
        default to posted entries only.

        Setting opening_debit/opening_credit on an account.account (in
        _combine001_import_accounts) doesn't build the opening move
        synchronously - it queues a precommit callback that only runs at
        cr.commit() time. Calling env.cr.flush() here forces that
        callback to run immediately (without actually committing the
        transaction), so company.account_opening_move_id is populated by
        the time this method reads it - otherwise it's still empty and
        this silently does nothing."""
        self.env.cr.flush()
        move = company.account_opening_move_id
        if move and move.state == 'draft' and move.line_ids:
            move.action_post()
            _logger.info("Combine001: opening balance journal entry posted (%s lines).", len(move.line_ids))

    def _combine001_archive_stale_accounts(self, company, imported_codes):
        """Archive accounts that exist for this company but are NOT part
        of this import (e.g. left over from a chart template loaded
        before this module, or a code removed from a later version of the
        source data). Never touches the accounts this import just
        created-or-updated, so re-running never produces duplicate codes."""
        Account = self.env['account.account']
        stale = Account.search([('company_ids', 'in', company.id), ('code', 'not in', list(imported_codes))])
        if stale:
            stale.write({'active': False})
            _logger.warning(
                "Combine001: archived %s account(s) not present in the imported Chart of Accounts. "
                "Default accounts on journals, taxes, product categories or fiscal positions may "
                "still point at them - review Accounting > Configuration before go-live.",
                len(stale),
            )

    # -- partners -----------------------------------------------------------

    def _combine001_import_partners(self, company, filename, account_code_field, account_by_code,
                                     customer_rank, supplier_rank, property_field):
        rows = _read_csv(filename)
        Partner = self.env['res.partner']
        existing = {p.name: p for p in Partner.search([
            '|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0),
        ])}
        fallback_code = _GENERAL_DEBTOR_CODE if property_field == 'property_account_receivable_id' else _GENERAL_CREDITOR_FALLBACK_CODE

        to_create = []
        for row in rows:
            account_id = account_by_code.get(row[account_code_field]) or account_by_code.get(fallback_code)
            vals = {
                'name': row['name'],
                'company_type': 'company',
                'customer_rank': customer_rank,
                'supplier_rank': supplier_rank,
            }
            if account_id:
                vals[property_field] = account_id

            found = existing.get(row['name'])
            if found:
                found.write(vals)
            else:
                to_create.append(vals)
        if to_create:
            Partner.create(to_create)
