# -*- coding: utf-8 -*-

from odoo import models, fields,api


class ProductSupplierInfo(models.Model):
    _inherit = 'product.supplierinfo'

    hts_codes_ids = fields.Many2many('product.hts.code',string='HTS Code')

ProductSupplierInfo()
