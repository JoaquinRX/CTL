from odoo import api, models, fields
from enum import Enum


class ProjectType(Enum):
    WAREHOUSE = 'Warehouse'
    GENERAL = 'General'


class ProjectInherit(models.Model):
    _name = 'project.project'
    _inherit = 'project.project'

    rx_project_type = fields.Selection(
        [(type.value, type.value) for type in ProjectType],
        string='Type',
        required=True,
        default=ProjectType.GENERAL.value)

    rx_is_warehouse = fields.Boolean(string="Is warehouse", compute='_compute_is_warehouse', readonly=True, store=True)
    rx_warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse pair")
    rx_available_stock_ids = fields.Many2many('stock.quant', compute='_compute_stock', store=True)

    @api.depends('rx_project_type')
    def _compute_is_warehouse(self):
        for project in self:
            project.rx_is_warehouse = project.rx_project_type == ProjectType.WAREHOUSE.value

    @api.depends('rx_warehouse_id')
    def _compute_stock(self):
        self.rx_available_stock_ids = self.env['stock.quant'].search([
            ('location_id.warehouse_id.id', '=', self.rx_warehouse_id.id)
        ])

    def write(self, values):
        result = super(ProjectInherit, self).write(values)

        if 'rx_warehouse_id' in values:
            warehouses = self.env['stock.warehouse'].search([])
            warehouses.compute_linked_project()
        return result


class TaskInherit(models.Model):
    _name = 'project.task'
    _inherit = 'project.task'

    rx_project_type = fields.Selection(string="Type", related='project_id.rx_project_type')
    rx_is_warehouse = fields.Boolean(string="Is warehouse", related='project_id.rx_is_warehouse', readonly=True)
    rx_available_stock_ids = fields.Many2many(related='project_id.rx_available_stock_ids', string='Stock')
    rx_task_quant_ids = fields.One2many('project.task.quant', 'rx_task_id', string='Task Quants')

    rx_ticket = fields.Char(string="Ticket")
    rx_order_type = fields.Selection(
        [
            ('assets purchase', 'Asset purchase'),
            ('returns', 'Returns'),
            ('assets request', 'Assets request'),
            ('re-stock deposit', 'Re-stock deposit'),
        ], string="Order type")

    rx_back_crum_node = fields.Boolean(string="Bring back CRUM/NODE")
    rx_refund_type = fields.Selection(
        [
            ('home pick-up', 'Home pick-up'),
            ('leave in deposit', 'Leave in deposit'),
        ], string="Refund type")

    rx_partner_id = fields.Many2one('res.partner', string="Origin")
    rx_direction = fields.Many2one('res.partner', string="Direction")
    rx_logistic = fields.Selection(
        [
            ('ctl logistic', 'CTL Logistic'),
            ('osde logistic', 'OSDE Logistic'),
            ('pick-up', 'Pick-up'),
        ], string="Logistic")

    rx_final_location = fields.Many2one('stock.warehouse', string="Final location")
    rx_date_of_receipt = fields.Date(string="Estimated date of receipt")
    rx_provider = fields.Many2one('res.partner', string="Provider")


class TaskQaunt(models.Model):
    _name = 'project.task.quant'

    rx_task_id = fields.Many2one('project.task', string='Task', readonly=True)
    rx_available_stock_ids = fields.Many2many(related='rx_task_id.rx_available_stock_ids', string='Stock')
    rx_stock_quant_id = fields.Many2one('stock.quant', string='Stock', domain="[('id', 'in', rx_available_stock_ids)]")
    rx_qty = fields.Integer('Quantity', default=1)
