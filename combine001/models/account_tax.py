from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    x_combine001_gst = fields.Boolean(
        string='Combine001 GST Tax', default=False,
        help='Marks this as one of the 4 GST taxes this module manages '
             '(Sale/Purchase x 18%/22%), so the GST Saving calculation on '
             'invoice/bill posting knows which taxes count as "GST was '
             'charged" versus falling back to the notional GST-saved '
             'calculation.',
    )
