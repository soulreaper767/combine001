from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_max_order_qty = fields.Float(
        string='Max Order Quantity',
        help='Maximum quantity allowed on a single Sales Order line for this '
             'product (BRD req. QC-001). Leave at 0 for no limit.',
    )
