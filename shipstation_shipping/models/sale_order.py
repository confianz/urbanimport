# -*- coding: utf-8 -*-

import json
import logging
import requests
from requests.auth import HTTPBasicAuth

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_shipstation_order = fields.Boolean(string="Order from Shipstation?", default=False, copy=False)
    is_shipstation_shipping = fields.Boolean(string="Shipstation Shipping?", default=False, copy=False)
    shipstation_account_id = fields.Many2one('shipstation.account', string="ShipStation Account", copy=False)
    shipstation_carrier_id = fields.Many2one('shipstation.carrier', string="ShipStation Carrier", copy=False)
    shipstation_service_id = fields.Many2one('shipstation.service', string="ShipStation Service", copy=False)
    shipstation_package_id = fields.Many2one('shipstation.package', string="ShipStation Package", copy=False)

    shipstation_order_id = fields.Char(string="ShipStation Order ID", copy=False)
    shipstation_order_key = fields.Char(string="ShipStation Order Key", copy=False)
    shipstation_order_state = fields.Selection([('waiting', 'Awaiting Shipment'), ('shipped', 'Shipped')], copy=False)
    shipstation_tracking_number = fields.Char("Tracking Reference", copy=False)

    weight = fields.Float(compute="_compute_weight", string="Shipment Weight", store=False)
    weight_uom_name = fields.Char(string="Weight UoM", compute='_compute_weight_uom_name', store=False)

    @api.depends('order_line', 'order_line.product_id', 'order_line.product_uom_qty')
    def _compute_weight(self):
        for order in self:
            weight = 0.0
            for line in order.order_line:
                if line.product_id and line.product_id.type != 'service':
                    weight += line.product_id.weight * line.product_uom_qty
            order.weight = weight

    def _compute_weight_uom_name(self):
        for order in self:
            order.weight_uom_name = self.env['product.template']._get_weight_uom_name_from_ir_config_parameter()

    def update_order_from_shipstation_webhook(self, resource_url, account):
        if not account:
            return True
        account = self.env['shipstation.account'].browse(account)
        headers = {
            'Content-Type': 'application/json'
        }
        shipments = []
        try:
            req = requests.request('GET', resource_url, auth=HTTPBasicAuth(account.api_key, account.api_secret), headers=headers)
            req.raise_for_status()
            response_text = req.text
        except requests.HTTPError as e:
            response = json.loads(req.text)
            error_msg = ''
            if response.get('ExceptionMessage', False):
                error_msg = response.get('ExceptionMessage', False)
            raise ValidationError(_("Error From ShipStation Webhook: %s" % error_msg or req.text))
        response = json.loads(response_text)
        shipment_data = response.get('shipments')
        if isinstance(shipment_data, dict):
            shipments += [shipment_data]
        shipments += shipment_data
        if shipments:
            self.update_shipstation_order(shipments, account)
        return shipments

    def update_shipstation_order(self, shipments, account):
        for shipment in shipments:
            try:
                orderId = shipment.get('orderId')
                if orderId:
                    SaleOrder = self.search([('shipstation_order_id','=', orderId)], limit=1)
                    if shipment.get('trackingNumber') and SaleOrder:
                        vals = {
                            'shipstation_tracking_number': shipment.get('trackingNumber'),
                            'shipstation_order_state': 'shipped',
                        }
                        SaleOrder.write(vals)
                        self.env.cr.commit()
            except Exception as e:
                self.env.cr.rollback()
                logging.error(e)
        return True

    def _check_carrier_quotation(self, force_carrier_id=None):
        res = super(SaleOrder, self)._check_carrier_quotation(force_carrier_id)
        DeliveryCarrier = self.env['delivery.carrier']
        if force_carrier_id:
            carrier_id = DeliveryCarrier.browse(force_carrier_id)
            if carrier_id and carrier_id.delivery_type == 'shipstation':
                self.write({
                    'is_shipstation_shipping': True,
                    'shipstation_service_id': carrier_id.shipstation_service_id.id,
                    'shipstation_carrier_id': carrier_id.shipstation_service_id.carrier_id.id,
                    'shipstation_package_id': carrier_id.default_package_id.id
                })
        return res


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

