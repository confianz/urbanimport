from odoo import models, fields, api


class Product(models.Model):
    _inherit = 'product.template'

    edi_customer_ids = fields.One2many('edi.customer', 'product_id', string="EDI Customer")


class EdiCustomer(models.Model):
    _name = 'edi.customer'

    product_id = fields.Many2one('product.template', string="Product")
    partner_id = fields.Many2one('res.partner', string="Customer")
    sku_productid = fields.Char("SKU ID")
