import csv
import logging
import os
from datetime import date

_logger = logging.getLogger(__name__)

_IMPORT_DIR = os.path.join(os.path.dirname(__file__), 'data', 'import')

_GENERAL_DEBTOR_CODE = '3.09.01'
_GENERAL_CREDITOR_FALLBACK_CODE = '2.07.09'

_OPENING_DATE = date(2026, 9, 16)


def _read_csv(filename):
    path = os.path.join(_IMPORT_DIR, filename)
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def post_init_hook(env):
    company = env.company
    _logger.info("Combine001: importing Chart of Accounts and opening trial balance for company %s", company.name)

    _cancel_generic_coa_auto_install(env)
    _reset_existing_opening_move(env, company)
    _clear_existing_coa(env, company)
    _ensure_baseline_journals(env, company)
    _import_account_groups(env, company)
    account_by_code = _import_accounts(env, company)
    _import_partners(env, 'customers.csv', 'receivable_account_code', account_by_code,
                      customer_rank=1, supplier_rank=0, property_field='property_account_receivable_id')
    _import_partners(env, 'vendors.csv', 'payable_account_code', account_by_code,
                      customer_rank=0, supplier_rank=1, property_field='property_account_payable_id')

    if not company.account_opening_date:
        company.account_opening_date = _OPENING_DATE
    if not company.chart_template:
        company.chart_template = 'generic_coa'

    _logger.info("Combine001: import complete - %s accounts, opening move left in draft for review.",
                 len(account_by_code))


def _cancel_generic_coa_auto_install(env):
    """Installing the 'account' module (a combine001 dependency) queues a
    one-shot callback on the registry that auto-installs Odoo's fallback
    'Generic Chart of Accounts' template (with its own journals/accounts)
    the moment the *whole* module graph finishes loading - regardless of
    what this hook does. That callback was queued when chart_template was
    still unset, so setting chart_template afterward does not stop it; the
    only way to stop it is to remove the queued callback itself, which is
    exactly what should happen since this module replaces the CoA with the
    client's own."""
    if hasattr(env.registry, '_auto_install_template'):
        del env.registry._auto_install_template


def _reset_existing_opening_move(env, company):
    move = company.account_opening_move_id
    if move and move.state == 'posted':
        move.button_draft()


def _clear_existing_coa(env, company):
    old_groups = env['account.group'].search([('company_id', '=', company.root_id.id)])
    old_groups.unlink()

    old_accounts = env['account.account'].search([('company_ids', 'in', company.id)])
    if old_accounts:
        old_accounts.write({'active': False})
        _logger.warning(
            "Combine001: archived %s pre-existing account.account records. Default accounts on "
            "journals, taxes, product categories or fiscal positions may still point at them - "
            "a System Administrator/Accountant should review Accounting > Configuration > Journals "
            "and repoint defaults at the newly-imported accounts before go-live.",
            len(old_accounts),
        )


def _ensure_baseline_journals(env, company):
    """Cancelling the fallback chart-template auto-install (see
    _cancel_generic_coa_auto_install) means this company has literally no
    journals at all yet. The opening move needs an existing 'general' type
    journal (Miscellaneous Operations); day-to-day Sales Orders / Vendor
    Bills need a 'sale' / 'purchase' journal. Neither needs a specific
    default account (they fall back to product-category accounts), so both
    are safe to create without guessing at the client's real setup.

    Deliberately NOT created here: a Bank/Cash journal. The imported CoA
    has ~30 real, named bank accounts under 'CASH AND BANK BALANCE'
    (3.14.xx) and there is no way to know from the source data which one
    is the client's actual day-to-day operating account - guessing wrong
    would misdirect real payments. A System Administrator/Accountant must
    create that journal manually and point it at the correct account.
    """
    Journal = env['account.journal']
    for jtype, code, name in (
        ('general', 'MISC', 'Miscellaneous Operations'),
        ('sale', 'INV', 'Customer Invoices'),
        ('purchase', 'BILL', 'Vendor Bills'),
    ):
        if not Journal.search([('company_id', '=', company.id), ('type', '=', jtype)], limit=1):
            Journal.create({'name': name, 'code': code, 'type': jtype, 'company_id': company.id})


def _import_account_groups(env, company):
    rows = _read_csv('account_groups.csv')
    vals_list = [{
        'name': row['name'],
        'code_prefix_start': row['code'],
        'code_prefix_end': row['code'],
        'company_id': company.root_id.id,
    } for row in rows]
    env['account.group'].create(vals_list)


def _import_accounts(env, company):
    rows = _read_csv('accounts.csv')
    vals_list = []
    for row in rows:
        debit = float(row['opening_debit'] or 0)
        credit = float(row['opening_credit'] or 0)
        account_type = row['account_type']
        vals = {
            'code': row['code'],
            'name': row['name'],
            'account_type': account_type,
            'company_ids': [(6, 0, [company.id])],
        }
        if account_type in ('asset_receivable', 'liability_payable'):
            vals['reconcile'] = True
        if debit:
            vals['opening_debit'] = debit
        if credit:
            vals['opening_credit'] = credit
        vals_list.append(vals)

    accounts = env['account.account'].create(vals_list)
    return {account.code: account.id for account in accounts}


def _import_partners(env, filename, account_code_field, account_by_code, customer_rank, supplier_rank, property_field):
    rows = _read_csv(filename)
    vals_list = []
    for row in rows:
        account_id = account_by_code.get(row[account_code_field])
        if not account_id:
            fallback_code = _GENERAL_DEBTOR_CODE if property_field == 'property_account_receivable_id' else _GENERAL_CREDITOR_FALLBACK_CODE
            account_id = account_by_code.get(fallback_code)
        vals = {
            'name': row['name'],
            'company_type': 'company',
            'customer_rank': customer_rank,
            'supplier_rank': supplier_rank,
        }
        if account_id:
            vals[property_field] = account_id
        vals_list.append(vals)
    env['res.partner'].create(vals_list)
