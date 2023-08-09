from odoo import api, models, fields
from enum import Enum


class ProjectType(Enum):
    WAREHOUSE = 'Warehouse'
    GENERAL = 'General'


class ProjectInherit(models.Model):
    _name = 'project.project'
    _inherit = 'project.project'

    project_type = fields.Selection(
        [(type.value, type.value) for type in ProjectType],
        string='Type',
        required=True,
        default=ProjectType.GENERAL.value)

    is_warehouse = fields.Boolean(string="Is warehouse", compute='_compute_is_warehouse', readonly=True, store=True)
    warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse pair")

    @api.depends('project_type')
    def _compute_is_warehouse(self):
        for project in self:
            project.is_warehouse = project.project_type == ProjectType.WAREHOUSE.value

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        warehouses = self.env['stock.warehouse'].search([])
        warehouses.compute_linked_project()

    def write(self, values):
        result = super(ProjectInherit, self).write(values)

        if 'warehouse_id' in values:
            warehouses = self.env['stock.warehouse'].search([])
            warehouses.compute_linked_project()

        return result


class TaskInherit(models.Model):
    _name = 'project.task'
    _inherit = 'project.task'

    project_type = fields.Selection(string="Type", related='project_id.project_type')
    is_warehouse = fields.Boolean(string="Is warehouse", related='project_id.is_warehouse', readonly=True)
