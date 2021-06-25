# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ShipstationService(models.Model):
    _name = "shipstation.service"
    _description = "Shipstation Services"

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", copy=False)
    is_domestic = fields.Boolean(string="Domestic?")
    is_international = fields.Boolean(string="International?")
    carrier_code = fields.Char(string="Carrier Code", copy=False)
    carrier_id = fields.Many2one('shipstation.carrier', string="Shipstation Carrier", ondelete="cascade")
    active = fields.Boolean(default=True, copy=False)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
