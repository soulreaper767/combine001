from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .commission_agent import COMMISSION_BASE_SELECTION


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_price_approval_state = fields.Selection([
        ('none', 'No Change'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='none', copy=False, tracking=True, string='Price Approval Status',
        help='Set automatically when a Sales User changes an item price away '
             'from the originally quoted price (BRD req. SO-001 to SO-004). '
             'The order cannot be confirmed while this is Pending Approval.')

    commission_agent_id = fields.Many2one('combine001.commission.agent', string='Commission Agent', tracking=True)
    commission_rate = fields.Float(string='Commission Rate (%)')
    commission_base = fields.Selection(COMMISSION_BASE_SELECTION, string='Commission Base')

    @api.onchange('commission_agent_id')
    def _onchange_combine001_commission_agent_id(self):
        if self.commission_agent_id:
            self.commission_rate = self.commission_agent_id.default_rate
            self.commission_base = self.commission_agent_id.default_base

    def _combine001_flag_price_change(self, line):
        self.ensure_one()
        is_manager = self.env.user.has_group('sales_team.group_sale_manager')
        if is_manager:
            if self.x_price_approval_state != 'approved':
                self.x_price_approval_state = 'approved'
            self.message_post(body=_(
                "Price on %(product)s changed to %(price)s by Sales Manager "
                "%(user)s (auto-approved).",
                product=line.product_id.display_name, price=line.price_unit,
                user=self.env.user.name,
            ))
        else:
            self.x_price_approval_state = 'pending'
            self.message_post(body=_(
                "Price on %(product)s changed from %(old)s to %(new)s by "
                "%(user)s. Sales Manager approval is required before this "
                "order can be confirmed.",
                product=line.product_id.display_name, old=line.x_quoted_price,
                new=line.price_unit, user=self.env.user.name,
            ))

    def action_combine001_approve_price(self):
        for order in self:
            if not self.env.user.has_group('sales_team.group_sale_manager'):
                raise UserError(_('Only a Sales Manager can approve a price change.'))
            order.x_price_approval_state = 'approved'
            order.message_post(body=_('Price change approved by %s.', self.env.user.name))

    def action_combine001_reject_price(self):
        for order in self:
            if not self.env.user.has_group('sales_team.group_sale_manager'):
                raise UserError(_('Only a Sales Manager can reject a price change.'))
            order.x_price_approval_state = 'rejected'
            order.message_post(body=_('Price change rejected by %s.', self.env.user.name))

    def action_confirm(self):
        for order in self:
            if order.x_price_approval_state == 'pending':
                raise UserError(_(
                    'Order %s has a price change pending Sales Manager '
                    'approval and cannot be confirmed yet.', order.name))
        return super().action_confirm()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    x_quoted_qty = fields.Float(
        copy=False, string='Originally Quoted Qty',
        help='Snapshot of the quantity the first time this line was created. '
             'Used to enforce that the confirmed Sales Order quantity does '
             'not exceed the quotation quantity (BRD req. SO-005/SO-006).')
    x_quoted_price = fields.Float(copy=False, string='Originally Quoted Price')
    x_is_charge_line = fields.Boolean(copy=False, string='Is Additional Charge')

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.product_id and not line.display_type:
                if not line.x_quoted_qty:
                    line.x_quoted_qty = line.product_uom_qty
                if not line.x_quoted_price:
                    line.x_quoted_price = line.price_unit
        return lines

    def write(self, vals):
        res = super().write(vals)
        if 'price_unit' in vals:
            for line in self:
                if line.display_type or not line.product_id or line.x_is_charge_line:
                    continue
                if (line.order_id.state in ('draft', 'sent')
                        and line.x_quoted_price
                        and line.price_unit != line.x_quoted_price):
                    line.order_id._combine001_flag_price_change(line)
        return res

    @api.constrains('product_uom_qty')
    def _check_combine001_quantities(self):
        for line in self:
            if line.display_type or not line.product_id or line.x_is_charge_line:
                continue

            if line.x_quoted_qty and line.product_uom_qty > line.x_quoted_qty:
                raise ValidationError(_(
                    "%(product)s: quantity %(qty)s exceeds the originally "
                    "quoted quantity of %(quoted)s. A Sales Order quantity "
                    "cannot exceed the quotation quantity.",
                    product=line.product_id.display_name, qty=line.product_uom_qty,
                    quoted=line.x_quoted_qty,
                ))

            max_qty = line.product_id.x_max_order_qty
            if max_qty and line.product_uom_qty > max_qty:
                raise ValidationError(_(
                    "%(product)s: quantity %(qty)s exceeds the configured "
                    "maximum order quantity of %(max)s for this item.",
                    product=line.product_id.display_name, qty=line.product_uom_qty,
                    max=max_qty,
                ))

            if line.order_id.partner_id:
                cust_limit = self.env['combine001.customer.item.limit'].search([
                    ('partner_id', '=', line.order_id.partner_id.id),
                    ('product_id', '=', line.product_id.id),
                ], limit=1)
                if cust_limit and line.product_uom_qty > cust_limit.max_qty:
                    raise ValidationError(_(
                        "%(product)s: quantity %(qty)s exceeds the maximum "
                        "quantity of %(max)s configured for customer "
                        "%(partner)s.",
                        product=line.product_id.display_name, qty=line.product_uom_qty,
                        max=cust_limit.max_qty, partner=line.order_id.partner_id.display_name,
                    ))
