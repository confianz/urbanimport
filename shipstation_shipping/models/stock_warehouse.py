# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    shipstation_warehouse_ids = fields.One2many('shipstation.warehouse', 'warehouse_id', string="Shipstation Warehouses")


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
