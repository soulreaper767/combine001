from odoo import fields, models


class Combine001Record(models.Model):
    _name = 'combine001.record'
    _description = 'Combine001 Record'
    _order = 'id desc'

    name = fields.Char(required=True)
    note = fields.Text()
    active = fields.Boolean(default=True)
