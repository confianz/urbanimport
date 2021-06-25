from odoo import api, fields, models, tools, _

class ProductImage(models.Model):
    _inherit = 'product.image'
    _description = "Product Image"

    bc_product_image_id = fields.Char(string='BC Product Image Id')
