# -*- coding: utf-8 -*-
##############################################################################
# Copyright (c) 2015-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>
##############################################################################
from odoo import models
from odoo.exceptions import ValidationError


class ExportProducts(models.TransientModel):
    _inherit = "export.products"

    def export_ebay_products(self):
        raise ValidationError('You can not export individual products in ebay')
