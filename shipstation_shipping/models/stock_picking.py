# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    shipstation_order_id = fields.Char(string="ShipStation Order ID", copy=False)
    shipstation_order_key = fields.Char(string="ShipStation Order Key", copy=False)

    def action_assign(self):
        res = super(StockPicking, self).action_assign()
        self.process_shipstation_shipping()
        return res

    def _action_done(self):
        res = super(StockPicking, self)._action_done()
        print(1010101010101)
        self.process_shipstation_shipping()
        return res

    def process_shipstation_shipping(self):
        for picking in self:
            sale_order = picking.sale_id
            ss_account = sale_order.shipstation_account_id
            ss_warehouse = sale_order.warehouse_id.shipstation_warehouse_ids[:1]
            if sale_order.is_shipstation_shipping and ss_warehouse.picking_type_id == picking.picking_type_id and ss_warehouse.picking_state == picking.state:
                picking.create_shipstation_order()

    def create_shipstation_order(self):
        self.ensure_one()
        sale_order = self.sale_id
        order_vals = self.prepare_shipstation_order_data()
        res = sale_order.shipstation_account_id._create_order(order_vals)
        if res:
            self.write({
                'shipstation_order_id': res.get('orderId'),
                'shipstation_order_key': res.get('orderKey'),
            })

            sale_order.write({
                'shipstation_order_id': res.get('orderId'),
                'shipstation_order_key': res.get('orderKey'),
                'shipstation_order_state': 'waiting',
            })

    def prepare_shipstation_order_data(self):
        sale_order = self.sale_id
        ss_warehouse = sale_order.warehouse_id.shipstation_warehouse_ids[:1]

        items = []
        for line in self.move_line_ids:
            items.append({
                "sku": line.product_id.default_code or '',
                "name": line.product_id.name or '',
                "quantity": int(line.qty_done if self.state == 'done' else line.product_uom_qty),
                "unitPrice": line.move_id.sale_line_id.price_unit,
            })

        vals = {
            'orderNumber': sale_order.name,
            'orderDate': sale_order.date_order.strftime('%Y-%m-%d %H:%M:%S'),
            'orderStatus': 'awaiting_shipment',
            'customerUsername': sale_order.partner_id.name,
            'customerEmail': sale_order.partner_id.email,

            'carrierCode': sale_order.shipstation_carrier_id.code,
            'serviceCode': sale_order.shipstation_service_id.code,
            'packageCode': sale_order.shipstation_package_id.code,

            'weight': {
                'value': sale_order.weight,
                'units': sale_order.shipstation_account_id.weight_uom,
            },

            'billTo': {
                'name': sale_order.partner_invoice_id.name,
                'street1': sale_order.partner_invoice_id.street,
                'street2': sale_order.partner_invoice_id.street2 or 'null',
                'city': sale_order.partner_invoice_id.city,
                'state': sale_order.partner_invoice_id.state_id.code,
                'postalCode': sale_order.partner_invoice_id.zip,
                'country': sale_order.partner_invoice_id.country_id.code,
                'phone': sale_order.partner_invoice_id.phone,
            },

            'shipTo': {
                'name': self.partner_id.name,
                'street1': self.partner_id.street,
                'street2': self.partner_id.street2 or 'null',
                'city': self.partner_id.city,
                'state': self.partner_id.state_id.code,
                'postalCode': self.partner_id.zip,
                'country': self.partner_id.country_id.code,
                'phone': self.partner_id.phone,
            },
            'items': items,
            'advancedOptions' : {
                'warehouseId': ss_warehouse.shipstation_warehouse_id or null,
                # 'storeId' : sale_order.shipstation_store_id.store_id,
            },
        }
        if self.backorder_id and self.shipstation_order_id:
            vals.update({"advancedOptions" : {
                'mergedOrSplit': True,
                'parentId': int(self.shipstation_order_id),
                # 'storeId' : picking.shipstation_store_id.store_id,
            }})

        if self.shipstation_order_key:
            vals.update({'orderKey': self.shipstation_order_key})
        return vals

    def send_to_shipper(self):
        if self.carrier_id.delivery_type == 'shipstation':
            return False
        else:
            return super(StockPicking, self).send_to_shipper()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
