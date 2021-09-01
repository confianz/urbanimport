# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _


class ProviderShipStation(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[('shipstation', "ShipStation")], ondelete={'shipstation': lambda recs: recs.write({'delivery_type': 'fixed', 'fixed_price': 0})})
    shipstation_id = fields.Many2one('shipstation.account', string="ShipStation Account")
    shipstation_service_id = fields.Many2one('shipstation.service', string="Shipstation Service")
    shipstation_service_code = fields.Char("Shipstation Service Code")
    default_package_id = fields.Many2one('shipstation.package', string="Package")

    def shipstation_rate_shipment(self, order):
        rate_shipment = self.env['choose.delivery.carrier']
        rate_shipment_id = rate_shipment.create({
            'shipstation_account_id': self.shipstation_id.id,
            'shipstation_service_id': self.shipstation_service_id.id,
            'shipstation_carrier_id': self.shipstation_service_id.carrier_id.id,
            'shipstation_package_id': self.default_package_id.id,
            'order_id': order.id,
            'use_shipstation': True
        })

        price_dict = rate_shipment_id.with_context({'shipstation': True}).get_rate_from_shipstation()
        if 'price' in price_dict:
            success = True
            price = price_dict['price']
        else:
            success = False
            price = 0
        return {
            'success': success,
            'price': price,
            'warning_message': ''
        }
