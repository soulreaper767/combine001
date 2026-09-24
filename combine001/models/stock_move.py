from odoo import _, fields, models
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    x_contract_price = fields.Float(
        related='sale_line_id.price_unit', store=True, string='Contract Price',
        help='Read-only, mirrored from the Contract/Sales Order line (BRD sec. 7.4).')

    def _action_done(self, cancel_backorder=False):
        for move in self:
            sale_line = move.sale_line_id
            if sale_line and move.picking_type_id.code == 'outgoing' and move.quantity:
                already_done = sum(sale_line.move_ids.filtered(
                    lambda m: m.state == 'done' and m.id != move.id
                ).mapped('quantity'))
                new_total = already_done + move.quantity
                if new_total > sale_line.product_uom_qty:
                    raise UserError(_(
                        "Cumulative delivered quantity for %(product)s "
                        "(%(done)s) would exceed the Sales Order quantity "
                        "(%(ordered)s) on order %(order)s.",
                        product=sale_line.product_id.display_name,
                        done=new_total, ordered=sale_line.product_uom_qty,
                        order=sale_line.order_id.name,
                    ))
        return super()._action_done(cancel_backorder=cancel_backorder)
