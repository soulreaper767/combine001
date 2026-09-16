from odoo import _, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        invoices = self.filtered(lambda m: m.move_type == 'out_invoice')
        for move in invoices:
            move._combine001_check_invoice_qty()
        res = super().action_post()
        for move in invoices:
            move._combine001_create_commission_lines()
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
