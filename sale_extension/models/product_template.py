from odoo import api, fields, models, tools, _



class ProductTemplate(models.Model):
    _inherit = "product.template"
    inventory_type = fields.Char('Inventory Type')
    real_name = fields.Char('Real Name')



# class ProductProduct(models.Model):
#     _inherit = "product.product"
#
#
#     default_code = fields.Char('Internal Reference', index=True)
#
#     _sql_constraints = [
#         ('default_code_uniq', 'unique(default_code)', "A SKU can only be assigned to one product !"),
#     ]

