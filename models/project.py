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
    available_stock_ids = fields.Many2many('stock.quant', compute='_compute_stock', store=True)

    @api.depends('project_type')
    def _compute_is_warehouse(self):
        for project in self:
            project.is_warehouse = project.project_type == ProjectType.WAREHOUSE.value

    @api.depends('warehouse_id')
    def _compute_stock(self):
        matching_stock_quants = self.env['stock.quant'].search([
            ('location_id.warehouse_id.id', '=', self.warehouse_id.id)
        ])
        self.available_stock_ids = matching_stock_quants

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
    available_stock_ids = fields.Many2many(related='project_id.available_stock_ids', string='Stock')
    task_quant_ids = fields.One2many('project.task.quant', 'task_id', string='Task Quants')

    ticket = fields.Char(string="Ticket")
    order_type = fields.Selection(
        [
            ('assets purchase', 'Asset purchase'),
            ('returns', 'Returns'),
            ('assets request', 'Assets request'),
            ('re-stock deposit', 'Re-stock deposit'),
        ], string="Order type")

    back_crum_node = fields.Boolean(string="Bring back CRUM/NODE")
    refund_type = fields.Selection(
        [
            ('home pick-up', 'Home pick-up'),
            ('leave in deposit', 'Leave in deposit'),
        ], string="Refund type")

    partner_id = fields.Many2one('res.partner', string="Origin")
    direction = fields.Many2one('res.partner', string="Direction")
    logistic = fields.Selection(
        [
            ('ctl logistic', 'CTL Logistic'),
            ('osde logistic', 'OSDE Logistic'),
            ('pick-up', 'Pick-up'),
        ], string="Logistic")

    final_location = fields.Many2one('stock.warehouse', string="Final location")
    date_of_receipt = fields.Date(string="Estimated date of receipt")
    provider = fields.Many2one('res.partner', string="Provider")


class TaskQaunt(models.Model):
    _name = 'project.task.quant'

    task_id = fields.Many2one('project.task', string='Task', readonly=True)
    available_stock_ids = fields.Many2many(related='task_id.available_stock_ids', string='Stock')
    stock_quant_id = fields.Many2one('stock.quant', string='Stock', domain="[('id', 'in', available_stock_ids)]")
    qty = fields.Integer('Quantity')
