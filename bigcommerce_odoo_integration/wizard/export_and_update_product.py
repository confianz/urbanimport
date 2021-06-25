# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ExportandUpdateProductinBC(models.TransientModel):
    _name = "export.and.update.product.to.bc"
    _description = "Export and Update Product to Bigcommerce"

    @api.model
    def _count(self):
        return len(self._context.get('active_ids', []))

    bigcommerce_store_ids = fields.Many2many('bigcommerce.store.configuration','bc_store_export_and_update_product_rel',string='Bigcommerce Store')
    count = fields.Integer(default=_count, string='Order Count')

    # def update_product_in_bigcommerce(self):
    #     product_templates = self.env['product.template'].browse(self._context.get('active_ids', []))
    #     for bc_store in self.bigcommerce_store_ids:
    #         self.env['product.template'].update_product_in_bigcommerce_from_product(bc_store,product_templates)
    #
    # def export_product_in_bigcommerce(self):
    #     product_templates = self.env['product.template'].browse(self._context.get('active_ids', []))
    #     for bc_store in self.bigcommerce_store_ids:
    #         self.env['product.template'].export_product_in_bigcommerce_from_product(bc_store,product_templates)