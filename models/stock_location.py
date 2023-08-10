from odoo import models, fields


class LocationInherit(models.Model):
    _name = "stock.location"
    _inherit = "stock.location"

    warehouse_id = fields.Many2one('stock.warehouse', compute='_compute_warehouse_id', store=True)
