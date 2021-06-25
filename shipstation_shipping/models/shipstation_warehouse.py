# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ShipstationWarehouse(models.Model):
    _name = "shipstation.warehouse"
    _description = "Shipstation Ship From Locations"

    name = fields.Char(string="Warehouse Name", required=True)
    shipstation_warehouse_id = fields.Char(string="Warehouse ID")
    shipstation_account_id = fields.Many2one('shipstation.account', string="ShipStation Account")
    is_default = fields.Boolean(string="Default?", default=False)
    warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse")
    picking_type_id = fields.Many2one('stock.picking.type', string="Shipment Picking")
    picking_state = fields.Selection([('assigned', 'Ready'), ('done', 'Done')])


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
