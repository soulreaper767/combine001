from odoo import fields, models


class GstSavingLine(models.Model):
    _name = 'combine001.gst.saving.line'
    _description = 'GST Saving Line'
    _order = 'date desc, id desc'

    move_id = fields.Many2one('account.move', required=True, ondelete='cascade', string='Invoice/Bill')
    journal_entry_id = fields.Many2one('account.move', required=True, ondelete='cascade', string='GST Saving Entry')
    direction = fields.Selection([
        ('sale', 'Sale (no GST charged)'),
        ('purchase', 'Purchase (no GST paid)'),
    ], required=True)
    partner_id = fields.Many2one(related='move_id.partner_id', store=True, string='Partner')
    date = fields.Date(related='move_id.invoice_date', store=True)
    base_amount = fields.Monetary(string='Untaxed Amount')
    rate = fields.Float(string='GST Rate (%)')
    gst_amount = fields.Monetary(string='GST Saved')
    currency_id = fields.Many2one(related='move_id.currency_id', store=True)
    company_id = fields.Many2one(related='move_id.company_id', store=True)

    _move_id_uniq = models.Constraint(
        'UNIQUE(move_id)',
        'A GST saving entry already exists for this invoice/bill.',
    )
