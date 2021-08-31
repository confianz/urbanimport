# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta

EBAY_DATEFORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'


def _ebay_parse_date(s):  # should be fromisoformat starting with datetime 3.7
    return datetime.strptime(s, EBAY_DATEFORMAT)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_ebay_order = fields.Boolean("Is Ebay order")

    @api.model
    def _process_order_new(self, order):
        (partner, shipping_partner) = self._process_order_new_find_partners(order)
        fp = self.env['account.fiscal.position'].get_fiscal_position(partner.id, delivery_id=shipping_partner.id)
        if fp:
            partner.property_account_position_id = fp
        create_values = {
            'partner_id': partner.id,
            'partner_shipping_id': shipping_partner.id,
            'state': 'draft',
            'client_order_ref': order['OrderID'],
            'origin': 'eBay' + order['OrderID'],
            'fiscal_position_id': fp.id,
            'is_ebay_order': True,
            'date_order': _ebay_parse_date(order['PaidTime']),
        }
        if self.env['ir.config_parameter'].sudo().get_param('ebay_sales_team'):
            create_values['team_id'] = int(
                self.env['ir.config_parameter'].sudo().get_param('ebay_sales_team'))

        sale_order = self.env['sale.order'].create(create_values)

        for transaction in order['TransactionArray']['Transaction']:
            sale_order._process_order_new_transaction(transaction)

        sale_order._process_order_shipping(order)


SaleOrder()


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model
    def create(self, vals):
        line = super(SaleOrderLine, self).create(vals)
        if len(line.order_id.order_line.filtered(lambda o_line: o_line.product_id.type != 'service').ids) == 1:
            product_id = line.order_id.order_line.mapped('product_id')[0]
            qty = line.order_id.order_line.mapped('product_uom_qty')[0]
            if product_id.is_flat_rate and product_id.delivery_carrier_id == line.order_id.carrier_id and line.name == product_id.delivery_carrier_id.name:
                line.price_unit = product_id.flat_rate * qty
        return line

    def write(self, vals):
        if len(self.order_id.order_line.filtered(lambda o_line: o_line.product_id.type != 'service').ids) == 1:
            product_id = self.order_id.order_line.mapped('product_id')[0]
            qty = self.order_id.order_line.mapped('product_uom_qty')[0]
            if product_id.is_flat_rate and product_id.delivery_carrier_id == self.order_id.carrier_id and self.name == product_id.delivery_carrier_id.name:
                vals['price_unit'] = product_id.flat_rate * qty
        line = super(SaleOrderLine, self).write(vals)
        return line
