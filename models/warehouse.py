from odoo import models, fields


class WarehouseInherit(models.Model):
    _name = 'stock.warehouse'
    _inherit = 'stock.warehouse'

    project_id = fields.Many2one('project.project', string='Project pair', readonly=True)
