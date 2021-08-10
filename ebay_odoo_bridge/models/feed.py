# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2019-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import fields, models, api


class ProductVaraintFeed(models.Model):
    _inherit = 'product.variant.feed'

    ebay_description_html = fields.Text(
        string='Ebay HTML Description'
    )
    ebay_MPN = fields.Char("Ebay MPN")
    ebay_Brand = fields.Char("Ebay Brand")
    @api.model
    def get_product_fields(self):
        res = super(ProductVaraintFeed, self).get_product_fields()
        res += ['ebay_description_html', 'ebay_MPN', 'ebay_Brand']
        return res
