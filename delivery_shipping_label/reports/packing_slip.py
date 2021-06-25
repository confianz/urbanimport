# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ReportShippingLabel(models.AbstractModel):
    _name = 'report.delivery_shipping_label.report_shipping_label'

    @api.model
    def _get_report_values(self, docids, data=None):

        return {
            'doc_ids': docids,
            'doc_model': 'stock.picking',
            'data': data,
            'docs': self.env['stock.picking'].browse(docids),
        }
