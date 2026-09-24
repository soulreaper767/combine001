from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DeliveryOut(models.Model):
    """BRD sec. 6: a new document sitting between the confirmed Sales
    Order and the Delivery Challan (stock.picking). Purely a commercial/
    logistics reference document - it never touches stock (BRD sec. 6.2:
    'No stock shall be issued from the warehouse against the Sales Order
    or Delivery Out'), so this is a plain Odoo model with no stock.picking
    /stock.move involvement at all, not a stock document reused for
    something it isn't.
    """
    _name = 'combine001.delivery.out'
    _description = 'Delivery Out'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(default='New', copy=False, readonly=True)
    sale_order_id = fields.Many2one('sale.order', required=True, ondelete='cascade',
                                     string='Contract / Sales Order', tracking=True)
    partner_id = fields.Many2one(related='sale_order_id.partner_id', store=True, string='Customer')
    x_gst_status = fields.Selection(related='partner_id.x_gst_status', store=True, string='GST Status')
    x_income_tax_status = fields.Selection(related='partner_id.x_income_tax_status', store=True, string='Income Tax Status')
    x_pra_status = fields.Selection(related='partner_id.x_pra_status', store=True, string='PRA Status')
    x_show_pra_status = fields.Boolean(compute='_compute_x_show_pra_status')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], default='draft', copy=False, tracking=True)
    date = fields.Date(default=fields.Date.context_today)
    line_ids = fields.One2many('combine001.delivery.out.line', 'delivery_out_id', string='Lines')
    company_id = fields.Many2one(related='sale_order_id.company_id', store=True)
    currency_id = fields.Many2one(related='sale_order_id.currency_id')
    picking_ids = fields.One2many('stock.picking', 'x_delivery_out_id', string='Delivery Challans')
    picking_count = fields.Integer(compute='_compute_picking_count')

    @api.depends('line_ids.sale_line_id.product_id.x_pra_applicable')
    def _compute_x_show_pra_status(self):
        for rec in self:
            rec.x_show_pra_status = bool(rec.line_ids.sale_line_id.product_id.filtered('x_pra_applicable'))

    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = len(rec.picking_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('combine001.delivery.out') or 'New'
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if rec.sale_order_id.state != 'sale':
                raise UserError(_('The Contract/Sales Order must be confirmed first.'))
            rec.state = 'confirmed'
            rec.message_post(body=_('Delivery Out confirmed by %s. No stock has been issued.', self.env.user.name))

    def action_view_pickings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delivery Challans'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.picking_ids.ids)],
        }


class DeliveryOutLine(models.Model):
    _name = 'combine001.delivery.out.line'
    _description = 'Delivery Out Line'

    delivery_out_id = fields.Many2one('combine001.delivery.out', required=True, ondelete='cascade')
    sale_line_id = fields.Many2one(
        'sale.order.line', required=True, ondelete='restrict', string='Contract Line',
        domain="[('order_id', '=', parent.sale_order_id)]")
    product_id = fields.Many2one(related='sale_line_id.product_id', store=True)
    # Related + stored: automatically stays in sync if the Contract is
    # later amended (BRD sec. 3.3/12 - "changes...shall be reflected"
    # without any custom propagation code and, since there is exactly one
    # line per sale.order.line, without any possibility of a duplicate.
    product_uom_qty = fields.Float(related='sale_line_id.product_uom_qty', store=True, string='Quantity')
    price_unit = fields.Float(related='sale_line_id.price_unit', store=True, string='Contract Price')
    product_uom = fields.Many2one(related='sale_line_id.product_uom_id', store=True, string='UoM')
