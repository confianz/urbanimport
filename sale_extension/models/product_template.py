from odoo import api, fields, models, tools, _



class ProductTemplate(models.Model):
    _inherit = "product.template"
    inventory_type = fields.Char('Inventory Type')
    real_name = fields.Char('Real Name')


