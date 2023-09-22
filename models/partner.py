from odoo import api, models, fields


class PartnerInherit(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    rx_product_line_ids = fields.One2many('product.line', 'rx_partner_id', compute='_compute_product_line_ids')

    @api.depends('rx_product_line_ids', 'rx_product_line_ids.rx_qty')
    def _compute_product_line_ids(self):
        self.rx_product_line_ids = self.env['product.line']
        products = {}
        products_lots = {}
        for task in self.env['project.task'].search([('rx_partner_id', '=', self.id), ('stage_id.name', '=', 'Finalizado')]):
            inverter = 1
            if (task.rx_order_type == 'returns'):
                inverter = -1

            for line in task.rx_task_order_line_ids:
                product = line.rx_stock_quant_id.product_id.id
                if products.get(product):
                    products[product] += line.rx_qty * inverter
                else:
                    products[product] = line.rx_qty * inverter

                if products_lots.get(product):
                    products_lots[product] += line.rx_lot_ids.ids
                else:
                    products_lots[product] = line.rx_lot_ids.ids

        for key, value in products.items():
            product_id = self.env['product.product'].search([('id', '=', key)])
            line = self.env['product.line'].create({
                'rx_partner_id': self.id,
                'rx_product_name': product_id.name,
                'rx_product_id': key,
                'rx_qty': value,
                'rx_lot_ids': products_lots[key]
            })
            if not product_id == line.rx_product_id:
                self.rx_product_line_ids += line


class ProductLine(models.Model):
    _name = 'product.line'

    rx_partner_id = fields.Many2one('res.partner', string='Partner')

    rx_product_name = fields.Char(string='Product')
    rx_product_id = fields.Many2one('product.product', string='Product')
    rx_qty = fields.Integer('Quantity')
    rx_lot_ids = fields.Many2many('stock.production.lot')
