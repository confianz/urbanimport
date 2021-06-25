from odoo import models, fields


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    height = fields.Float("Height")
    width = fields.Float("Width")
    length = fields.Float("length")


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    height = fields.Float('Height')
    width = fields.Float('Width')
    length = fields.Float('Length')
