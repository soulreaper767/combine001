from odoo import fields, models


class CommissionLine(models.Model):
    _name = 'combine001.commission.line'
    _description = 'Commission Line'
    _order = 'date desc, id desc'

    agent_id = fields.Many2one('combine001.commission.agent', required=True, string='Commission Agent')
    sale_order_id = fields.Many2one('sale.order', required=True, ondelete='cascade', string='Sales Order')
    sale_line_id = fields.Many2one('sale.order.line', required=True, ondelete='cascade', string='Sales Order Line')
    invoice_id = fields.Many2one('account.move', required=True, ondelete='cascade', string='Invoice')
    invoice_line_id = fields.Many2one('account.move.line', required=True, ondelete='cascade', string='Invoice Line')
    partner_id = fields.Many2one(related='sale_order_id.partner_id', store=True, string='Customer')
    product_id = fields.Many2one(related='sale_line_id.product_id', store=True, string='Product')
    date = fields.Date(related='invoice_id.invoice_date', store=True)
    base = fields.Selection(related='sale_order_id.commission_base', store=True, string='Commission Base')
    base_amount = fields.Monetary(string='Base Amount')
    rate = fields.Float(string='Rate (%)')
    commission_amount = fields.Monetary(string='Commission Amount')
    currency_id = fields.Many2one(related='sale_order_id.currency_id', store=True)
    company_id = fields.Many2one(related='sale_order_id.company_id', store=True)

    _invoice_line_uniq = models.Constraint(
        'UNIQUE(invoice_line_id)',
        'A commission line already exists for this invoice line.',
    )
