from odoo import models, fields
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import UserError


class WarehouseInherit(models.Model):
    _name = 'stock.warehouse'
    _inherit = 'stock.warehouse'

    rx_project_id = fields.Many2one('project.project', string='Project pair', readonly=True, compute='compute_linked_project', store=True)

    def compute_linked_project(self):
        for warehouse in self:
            linked_project = self.env['project.project'].search([('rx_warehouse_id', '=', warehouse.id)], limit=1)
            warehouse.rx_project_id = linked_project.id if linked_project else False


class LocationInherit(models.Model):
    _name = "stock.location"
    _inherit = "stock.location"

    warehouse_id = fields.Many2one('stock.warehouse', compute='_compute_warehouse_id', store=True)  # existing field, added store=True


class StockQuantInherit(models.Model):
    _name = "stock.quant"
    _inherit = "stock.quant"

    available_quantity = fields.Float(readonly=True, store=True)
