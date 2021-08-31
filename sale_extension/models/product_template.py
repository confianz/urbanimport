from odoo import api, fields, models, tools, _



class ProductTemplate(models.Model):
    _inherit = "product.template"
    inventory_type = fields.Char('Inventory Type')
    real_name = fields.Char('Real Name')

    is_flat_rate = fields.Boolean('Is Flat Rate')
    flat_rate = fields.Float('Flat Rate')
    delivery_carrier_id = fields.Many2one('delivery.carrier')



# class ProductProduct(models.Model):
#     _inherit = "product.product"
#
#
#     default_code = fields.Char('Internal Reference', index=True)
#
#     _sql_constraints = [
#         ('default_code_uniq', 'unique(default_code)', "A SKU can only be assigned to one product !"),
#     ]

