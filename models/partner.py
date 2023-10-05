from odoo import api, models, fields


class PartnerInherit(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    rx_product_line_ids = fields.One2many('product.line', 'rx_partner_id', compute='_compute_product_line_ids')

    @api.depends('rx_product_line_ids', 'rx_product_line_ids.rx_qty')
    def _compute_product_line_ids(self):
        self.rx_product_line_ids = self.env['product.line']
        products = []
        assets_request_tasks = self.env['project.task'].search([('rx_partner_id', '=', self.id), ('stage_id.name', '=', 'Finalizado'), ('rx_order_type', '=', 'assets request')])
        for task in assets_request_tasks:
            for line in task.rx_task_order_line_ids:
                product_id = line.rx_stock_quant_id.product_id.id
                if not any(product_id == product.product_id for product in products):
                    products.append(Line(product_id, line.rx_qty, line.rx_lot_ids.ids))
                else:
                    for product in products:
                        if product.product_id == product_id:
                            product.qty += line.rx_qty
                            product.lot_ids += line.rx_lot_ids.ids

        return_tasks = self.env['project.task'].search([('rx_partner_id', '=', self.id), ('stage_id.name', '=', 'Finalizado'), ('rx_order_type', '=', 'returns')])
        for task in return_tasks:
            for line in task.rx_task_order_line_ids:
                product_id = line.rx_stock_quant_id.product_id.id
                if any(product_id == product.product_id for product in products):
                    for product in products:
                        if product.product_id == product_id:
                            product.qty -= line.rx_qty
                            if line.rx_lot_ids.id in product.lot_ids:
                                product.lot_ids.remove(line.rx_lot_ids.id)

        for product in products:
            product_id = self.env['product.product'].search([('id', '=', product.product_id)])
            line = self.env['product.line'].create({
                'rx_partner_id': self.id,
                'rx_product_name': product_id.name,
                'rx_product_id': product.product_id,
                'rx_qty': product.qty,
                'rx_lot_ids': product.lot_ids
            })


class ProductLine(models.Model):
    _name = 'product.line'

    rx_partner_id = fields.Many2one('res.partner', string='Partner')

    rx_product_name = fields.Char(string='Product')
    rx_product_id = fields.Many2one('product.product', string='Product')
    rx_qty = fields.Integer('Quantity')
    rx_lot_ids = fields.Many2many('stock.production.lot')


class Line:
    def __init__(self, product_id, qty, lot_ids=None):
        self.product_id = product_id
        self.qty = qty
        self.lot_ids = lot_ids
