from odoo import models, fields


class WarehouseInherit(models.Model):
    _name = 'stock.warehouse'
    _inherit = 'stock.warehouse'

    rx_project_id = fields.Many2one('project.project', string='Project pair', readonly=True, compute='compute_linked_project', store=True)

    def compute_linked_project(self):
        for warehouse in self:
            linked_project = self.env['project.project'].search([('rx_warehouse_id', '=', warehouse.id)], limit=1)
            warehouse.rx_project_id = linked_project.id if linked_project else False
