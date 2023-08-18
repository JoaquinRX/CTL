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

    @api.depends('rx_project_type')
    def _compute_is_warehouse(self):
        for project in self:
            project.rx_is_warehouse = project.rx_project_type == ProjectType.WAREHOUSE.value

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
    rx_task_order_line_ids = fields.One2many('project.task.order.line', 'rx_task_id', string='Task Quants')

    rx_is_warehouse = fields.Boolean(string="Is warehouse", related='project_id.rx_is_warehouse', readonly=True)
    rx_warehouse_id = fields.Many2one(related='project_id.rx_warehouse_id', readonly=True)

    rx_order_type = fields.Selection(
        [
            ('assets purchase', 'Asset purchase'),
            ('returns', 'Returns'),
            ('assets request', 'Assets request'),
            ('re-stock deposit', 'Re-stock deposit'),
        ], string="Order type", default='assets purchase', required=True)

    rx_ticket = fields.Char(string="Ticket")
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

    rx_final_location = fields.Many2one('stock.location', string="Final location")
    rx_date_of_receipt = fields.Date(string="Estimated date of receipt")
    rx_provider = fields.Many2one('res.partner', string="Provider")
    rx_partner_address = fields.Char('Address', compute='_onchange_partner_id', readonly=True)
    rx_origin_warehouse = fields.Many2one('stock.warehouse', string="Origin")
    rx_destination_warehouse = fields.Many2one('stock.warehouse', string="Destination")
    rx_multiple_locations = fields.Boolean(string="Multiple locations")
    rx_who_returns = fields.Selection(
        [
            ('crum', 'CRUM'),
            ('node', 'NODE'),
            ('user/collaborator', 'User/Collaborator'),
        ], string='Who returns')

    @api.onchange('rx_partner_id, partner_id')
    def _onchange_partner_id(self):
        if self.rx_partner_id:
            self.write({
                'rx_partner_address': self.partner_id.contact_address
            })

    @api.onchange('rx_task_order_line_ids', 'rx_order_type')
    def _onchange_task_quant_ids(self):
        quant_model = self.env['stock.quant']
        warehouse_id = self.rx_warehouse_id.id

        stock_quants = quant_model.search([
            ('location_id.warehouse_id', '=', warehouse_id)
        ])

        self.rx_task_order_line_ids.write({
            'rx_available_stock_ids': [(6, 0, stock_quants.ids)]
        })


class TaskOrderLine(models.Model):
    _name = 'project.task.order.line'

    rx_task_id = fields.Many2one('project.task', string='Task', readonly=True)
    rx_warehouse_id = fields.Many2one(related='rx_task_id.rx_warehouse_id', readonly=True)
    rx_task_order_type = fields.Selection(related='rx_task_id.rx_order_type')

    # ('assets purchase', 'Asset purchase'),
    # ('returns', 'Returns'),
    # ('assets request', 'Assets request'),
    # ('re-stock deposit', 'Re-stock deposit'),

    # assets request - re-stock deposit
    rx_available_stock_ids = fields.Many2many('stock.quant')
    rx_stock_quant_id = fields.Many2one('stock.quant', string='Stock', domain="[('id', 'in', rx_available_stock_ids)]")

    # assets purchase
    rx_product_template_ids = fields.Many2one('product.template', string='Product')

    # returns
    rx_qty = fields.Integer('Quantity', required=True, default=1)
