from odoo import api, models, fields


class PartnerInherit(models.Model):
    _name = "res.partner"
    _inherit = "res.partner"

    rx_stock_line_ids = fields.One2many(
        "stock.line", "rx_partner_id", compute="_compute_stock_line_ids"
    )

    @api.depends("rx_stock_line_ids", "rx_stock_line_ids.rx_qty")
    def _compute_stock_line_ids(self):
        self.rx_stock_line_ids = self.env["stock.line"]
        owned_quant = self.env["stock.quant"].search(
            [
                ("location_id.name", "=", "Customers"),
                ("owner_id", "=", self.id),
            ]
        )

        for quant in owned_quant:
            self.env["stock.line"].create(
                {
                    "rx_partner_id": self.id,
                    "rx_product_id": quant.product_id.id,
                    "rx_qty": quant.available_quantity,
                    "rx_lot_id": quant.lot_id.id,
                }
            )


class StockLine(models.Model):
    _name = "stock.line"

    rx_partner_id = fields.Many2one("res.partner", string="Partner")

    rx_product_id = fields.Many2one("product.product", string="Product")
    rx_qty = fields.Integer("Quantity")
    rx_lot_id = fields.Many2one("stock.production.lot")


class Line:
    def __init__(self, product_id, qty, lot_id=None):
        self.product_id = product_id
        self.qty = qty
        self.lot_id = lot_id
