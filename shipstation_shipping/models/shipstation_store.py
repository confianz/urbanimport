# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ShipstationStore(models.Model):
    _name = "shipstation.store"
    _description = "Shipstation Store"

    name = fields.Char(string="Name", required=True)
    store_id = fields.Char(string="Store ID", copy=False)
    marketplace_name = fields.Char(string="Marketplace Name", copy=False)
    marketplace_id = fields.Char(string="Marketplace ID", copy=False)
    company_name = fields.Char(string="Company Name", copy=False)
    account_name = fields.Char(string="Account Name", copy=False)
    shipstation_account_id = fields.Many2one('shipstation.account', string="ShipStation Account")
    active = fields.Boolean(default=True, copy=False)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
