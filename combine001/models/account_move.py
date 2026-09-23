from odoo import _, models
from odoo.exceptions import UserError

from .combine001_constants import GST_SAVING_ASSET_CODE, GST_SAVING_EQUITY_CODE

_GST_MOVE_TYPES = ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        invoices = self.filtered(lambda m: m.move_type == 'out_invoice')
        gst_relevant = self.filtered(lambda m: m.move_type in _GST_MOVE_TYPES)
        for move in invoices:
            move._combine001_check_invoice_qty()
        res = super().action_post()
        for move in invoices:
            move._combine001_create_commission_lines()
        for move in gst_relevant:
            move._combine001_create_gst_saving_line()
        return res

    def _combine001_check_invoice_qty(self):
        self.ensure_one()
        for line in self.invoice_line_ids:
            sale_line = line.sale_line_ids[:1]
            if not sale_line:
                continue
            other_qty = sum(self.env['account.move.line'].search([
                ('sale_line_ids', 'in', sale_line.id),
                ('move_id.state', '=', 'posted'),
                ('move_id.move_type', '=', 'out_invoice'),
                ('id', '!=', line.id),
            ]).mapped('quantity'))
            if other_qty + line.quantity > sale_line.product_uom_qty:
                raise UserError(_(
                    "Cumulative invoiced quantity for %(product)s "
                    "(%(total)s) would exceed the Sales Order quantity "
                    "(%(ordered)s) on order %(order)s.",
                    product=sale_line.product_id.display_name,
                    total=other_qty + line.quantity, ordered=sale_line.product_uom_qty,
                    order=sale_line.order_id.name,
                ))

    def _combine001_create_commission_lines(self):
        self.ensure_one()
        CommissionLine = self.env['combine001.commission.line']
        for line in self.invoice_line_ids:
            sale_line = line.sale_line_ids[:1]
            if not sale_line:
                continue
            order = sale_line.order_id
            if not order.commission_agent_id:
                continue
            if CommissionLine.search_count([('invoice_line_id', '=', line.id)]):
                continue
            base = order.commission_base or order.commission_agent_id.default_base
            rate = order.commission_rate or order.commission_agent_id.default_rate
            base_amount = line.quantity if base == 'quantity' else line.price_subtotal
            commission_amount = base_amount * (rate or 0.0) / 100.0
            CommissionLine.create({
                'agent_id': order.commission_agent_id.id,
                'sale_order_id': order.id,
                'sale_line_id': sale_line.id,
                'invoice_id': self.id,
                'invoice_line_id': line.id,
                'base_amount': base_amount,
                'rate': rate,
                'commission_amount': commission_amount,
            })

    def _combine001_create_gst_saving_line(self):
        """If this invoice/bill has NO GST charged on it at all, compute
        what GST would have applied - using the rate configured on each
        line's product master (sale: taxes_id, purchase: supplier_taxes_id,
        whichever of the 4 GST taxes this module manages is set there) -
        and record it as "GST Saved": a same-amount Dr GST Saving (Current
        Asset) / Cr GST Saving Reserve (Equity) entry, kept entirely
        outside the real P&L (it never touches an income/expense account),
        purely for management visibility into the value of off-GST-books
        trade. A line whose product has no GST tax configured at all
        contributes nothing (there's no rate to use)."""
        self.ensure_one()
        if self.move_type not in _GST_MOVE_TYPES:
            return
        if self.env['combine001.gst.saving.line'].search_count([('move_id', '=', self.id)]):
            return

        is_sale = self.move_type in ('out_invoice', 'out_refund')
        tax_field = 'taxes_id' if is_sale else 'supplier_taxes_id'

        total_base = 0.0
        total_gst = 0.0
        for line in self.invoice_line_ids:
            if not line.product_id:
                continue
            if any(t.x_combine001_gst for t in line.tax_ids):
                continue  # real GST already charged on this line
            product_gst_taxes = line.product_id[tax_field].filtered('x_combine001_gst')
            if not product_gst_taxes:
                continue  # no GST rate configured on this product to fall back on
            rate = product_gst_taxes[0].amount
            total_base += line.price_subtotal
            total_gst += line.price_subtotal * rate / 100.0

        if not total_gst:
            return

        company = self.company_id
        Account = self.env['account.account']
        asset_account = Account.search([
            ('company_ids', 'in', company.id), ('code', '=', GST_SAVING_ASSET_CODE),
        ], limit=1)
        equity_account = Account.search([
            ('company_ids', 'in', company.id), ('code', '=', GST_SAVING_EQUITY_CODE),
        ], limit=1)
        journal = self.env['account.journal'].search([
            ('company_id', '=', company.id), ('type', '=', 'general'),
        ], limit=1)
        if not (asset_account and equity_account and journal):
            return

        label = _("GST Saved - %(move)s", move=self.name or self.ref or 'Draft')
        entry = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': self.invoice_date or self.date,
            'ref': label,
            'line_ids': [
                (0, 0, {
                    'account_id': asset_account.id, 'partner_id': self.partner_id.id,
                    'name': label, 'debit': total_gst, 'credit': 0.0,
                }),
                (0, 0, {
                    'account_id': equity_account.id, 'partner_id': self.partner_id.id,
                    'name': label, 'debit': 0.0, 'credit': total_gst,
                }),
            ],
        })
        entry.action_post()

        self.env['combine001.gst.saving.line'].create({
            'move_id': self.id,
            'journal_entry_id': entry.id,
            'direction': 'sale' if is_sale else 'purchase',
            'base_amount': total_base,
            'rate': (total_gst / total_base * 100.0) if total_base else 0.0,
            'gst_amount': total_gst,
        })
