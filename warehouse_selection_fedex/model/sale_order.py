from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def find_set_delivery_line(self, carrier, price):
        if self.bigcommerce_store_id or self.is_ebay_order or self.is_amazon_order:
            carrier = self.env['delivery.carrier'].search(
                [('delivery_type', '=', 'shipstation'), ('shipstation_service_code', '=', 'usps_priority_mail')],
                limit=1)
            if not carrier:
                raise UserError(_('Please Define Shipstation Carrier Method with type - Fedex'))

            shp_service = self.env['shipstation.service'].search(
                [('code', '=', 'usps_priority_mail')],
                limit=1)
            if shp_service:
                shp_package = self.env['shipstation.package'].search(
                    [('code', '=', 'package'),('carrier_id', '=', shp_service.carrier_id.id)],
                    limit=1)
            self.write({
                'carrier_id': carrier.id,
                'is_shipstation_shipping': True,
                'shipstation_package_id': shp_package.id,
                'shipstation_service_id': shp_service and shp_service.id or False,
                'shipstation_carrier_id': shp_service and shp_service.carrier_id.id or False,
                'shipstation_account_id': carrier.shipstation_id.id,
            })
        else:
            self.set_delivery_line(carrier, price)
            self.write({
                'is_shipstation_shipping': False,
                'shipstation_package_id': False,
                'shipstation_service_id': False,
                'shipstation_carrier_id': False,
                'shipstation_account_id': False,
            })
        return True

    def max_qty_wh(self):
        product_id = self.order_line.mapped('product_id')[0]
        warehouses = self.env['stock.warehouse'].search([('warehouse_type', '=', 'main_warehouse'),('company_id', '=', self.company_id.id)])
        quantity = {}
        for warehouse_id in warehouses:
            qty = product_id.with_context(warehouse=warehouse_id.id).qty_available
            quantity[warehouse_id] = qty
        return quantity

    def update_warehouse(self, classification):
        warehouses = self.env['stock.warehouse'].search([('warehouse_type', '=', 'main_warehouse'),('company_id', '=', self.company_id.id)])
        if classification != 'BUSINESS':
            address_type = 'Residential'
            fedex_service_type = 'GROUND_HOME_DELIVERY'
        else:
            address_type = 'Non Residential'
            fedex_service_type = 'FEDEX_GROUND'
        carrier = self.env['delivery.carrier'].search(
            [('delivery_type', '=', 'fedex'), ('fedex_service_type', '=', fedex_service_type)], limit=1)
        if not carrier:
            raise UserError(_('Please Define Fedex Carrier Method with type - %s', fedex_service_type))
        price_dict = {}
        time_dict = {}
        quantity = self.max_qty_wh()
        for warehouse in warehouses:
            vals = carrier.fedex_rate_shipment_custom(self, warehouse)
            # print('vals----------------', vals)
            if not vals['success']:
                self.message_post(body=('Exception :- %s') % (vals['error_message']),
                                  subtype_id=self.env.ref('mail.mt_note').id)
                # print('----------------------------')
                return False
            price_dict[warehouse] = vals['price']
            time_dict[warehouse] = vals['time']
        # print('price_dict',price_dict)
        # print('time_dict',time_dict)
        if not len(list(set(list(time_dict.values())))) == 1:
            warehouse = min(time_dict, key=time_dict.get)
        elif not len(list(set(list(price_dict.values())))) == 1:
            warehouse = min(price_dict, key=price_dict.get)
        else:
            warehouse = max(quantity, key=quantity.get)
        self.find_set_delivery_line(carrier, price_dict[warehouse])

            # print('warehouse', warehouse)
        td = ''
        # print('quantityquantityquantity', quantity)
        for wh in warehouses:
            td += '<tr><td style="color:#008080;text-align:center;padding:0 12px 0 12px;">%s</td><td style="color:#008080;text-align:center;padding:0 12px 0 12px;">%s</td><td style="color:#008080;text-align:center;padding:0 12px 0 12px;">%s</td><td style="color:#008080;text-align:center;padding:0 12px 0 12px;">%s</td></tr>' % (
                wh.name, (time_dict[wh]).strftime("%m/%d/%Y, %H:%M"), price_dict[wh],
                quantity[wh])

        th = '<thead><tr><th style="text-align:center;padding:0 12px 0 12px;">Warehouse</th><th style="text-align:center;padding:0 12px 0 12px;">Delivery Date</th><th style="text-align:center;padding:0 12px 0 12px;">Rate</th><th style="text-align:center;padding:0 12px 0 12px;">Qty Available</th></tr></thead>'

        self.message_post(
            body=('<h4>Warehouse Selection Info:- </h4><h6>Classification Type - %s</h6><table>%s%s</table>') % (
                address_type, th, td),
            subtype_id=self.env.ref('mail.mt_note').id)
        return warehouse

    def check_avs_update_wh(self):
        self._remove_delivery_line()
        if len(self.order_line.filtered(lambda o_line: o_line.product_id.type != 'service').ids) == 1 and \
                self.order_line.mapped('product_uom_qty')[0] == 1:
            if self.partner_shipping_id.country_id != self.company_id.country_id:
                quantity = self.max_qty_wh()
                warehouse = max(quantity, key=quantity.get)
                if warehouse:
                    self.warehouse_id = warehouse.id
            else:
                fedex_carrier = self.env['delivery.carrier'].search([('delivery_type', '=', 'fedex')], limit=1)
                if not fedex_carrier:
                    raise UserError("Please Define Fedex Carrier Method")
                classification = fedex_carrier.fedex_validate_address(partner=self.partner_shipping_id)
                warehouse = self.update_warehouse(classification)
                # print('warehouse------',warehouse)
                if warehouse:
                    self.warehouse_id = warehouse.id
        return True

    @api.model
    def create(self, vals):
        order = super(SaleOrder, self).create(vals)
        if len(order.order_line.filtered(lambda o_line: o_line.product_id.type != 'service').ids) == 1 and \
                order.order_line.mapped('product_uom_qty')[0] == 1:
            if order.partner_shipping_id.country_id != order.company_id.country_id:
                quantity = self.max_qty_wh()
                warehouse = max(quantity, key=quantity.get)
                if warehouse:
                    order.warehouse_id = warehouse.id
            else:
                fedex_carrier = self.env['delivery.carrier'].search([('delivery_type', '=', 'fedex')], limit=1)
                classification = fedex_carrier.fedex_validate_address(partner=order.partner_shipping_id)
                warehouse = order.update_warehouse(classification)
                if warehouse:
                    order.warehouse_id = warehouse.id
        if order.bigcommerce_store_id or order.is_ebay_order or order.is_amazon_order:
            order.action_confirm()
        return order
