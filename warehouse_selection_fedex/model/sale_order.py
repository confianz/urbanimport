from odoo import api, fields, models, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
from datetime import datetime


class SaleOrder(models.Model):
    _inherit = "sale.order"

    log_note = fields.Text(string='Log - Warehouse Selection')

    def find_warehouse(self, cal_dicts, quantity, warehouses, log):
        prf_warehouse = {}
        incoming_shipment = self.upcoming_shipments(warehouses)
        for key, value in sorted(cal_dicts.items(),
                                 key=lambda item: item[1]):
            # print('cal_dictscal_dictscal_dicts', key)
            if quantity[key] > 0 and not prf_warehouse:
                log += 'Quantity exist and selecting warehouse ' + str(key.name) + '\n'
                warehouse = key
                return warehouse, log
            else:
                log += 'quantity does not exist, checking incoming shipments\n'
                result, log = self.check_incoming_on_warehouse(key, prf_warehouse, incoming_shipment, log)
                # print('result', result)
                if result['status']:
                    warehouse = key
                    return warehouse, log
                else:
                    if result[key]:
                        prf_warehouse[key] = result[key]
        new_prf_warehouse = dict((k, v) for k, v in prf_warehouse.items() if v)
        # if new_prf_warehouse:
        #     warehouse = min(new_prf_warehouse, key=new_prf_warehouse.get)
        # else:
        warehouse = False
        # print('new_prf_warehouse', new_prf_warehouse)
        return warehouse, log

    def check_incoming_on_warehouse(self, selected_warehouse, prf_warehouse, incoming_shipment, log):
        incoming_buffer_days = self.env['ir.config_parameter'].sudo().get_param('incoming_buffer_days') or 1
        if selected_warehouse.id in incoming_shipment:
            selected_warehouse_date = incoming_shipment[selected_warehouse.id]
            log += 'latest incoming shipment on ' + str(selected_warehouse_date) + ' for ' + str(
                selected_warehouse.name) + '\n'
            log += 'Buffer days ' + str(incoming_buffer_days) + '\n'
            today_date = datetime.now()
            # print('incoming_buffer_days', incoming_buffer_days)
            # print('selected_warehouse_date', selected_warehouse_date)
            result_dt = selected_warehouse_date - relativedelta(days=int(incoming_buffer_days))
            # print('result_dt--------', result_dt)
            # print('prf_warehouse--------', prf_warehouse)
            if prf_warehouse:
                log += 'Checking next warehouse \n' + str(
                    selected_warehouse.name)

                if all(value and value > selected_warehouse_date for value in prf_warehouse.values()):
                    log += 'Incoming date of next warehouse < stored date - Selecting next warehouse ' + str(
                        selected_warehouse.name) +'\n'
                    return {'status': True}, log
                else:
                    log += 'Checking next warehouse\n'
                    return {'status': False, selected_warehouse: selected_warehouse_date}, log
            else:
                if today_date >= result_dt:
                    log += 'Today date >= (incoming date - buffer)\n' + 'Selecting preferred Warehouse ' + str(
                        selected_warehouse.name)
                    return {'status': True}, log
                else:
                    log += 'Storing preferred Warehouse date + buffer time\n'
                    return {'status': False, selected_warehouse: result_dt}, log
        else:
            log += 'No incoming shipments for this warehouse ' + str(selected_warehouse.name) + '\n'
            return {'status': False, selected_warehouse: False}, log

    def upcoming_shipments(self, warehouses):
        product_id = self.order_line.mapped('product_id')[0]
        ocean_moves = self.env['stock.move'].search(
            [('picking_id.wh_transfer_done', '=', False), ('product_id', '=', product_id.id),
             ('warehouse_id.warehouse_type', '=', 'ocean'),
             ('state', 'not in', ['draft', 'cancel'])]).filtered(
            lambda x: x.purchase_line_id.order_id.end_loc_id.get_warehouse().id in warehouses.ids)
        direct_moves = self.env['stock.move'].search(
            [('product_id', '=', product_id.id),
             ('warehouse_id.warehouse_type', '=', 'main_warehouse'),
             ('picking_id.picking_type_id.code', '=', 'incoming'),
             ('picking_id.state', 'not in', ['done', 'cancel', 'draft'])]).filtered(
            lambda x: x.warehouse_id.id in warehouses.ids)
        # print('ocean_moves----------', ocean_moves)
        # print('ocean_moves.mapped('')----------', ocean_moves.mapped('picking_id'))
        # print('direct_moves----------', direct_moves)
        # print('direct_moves.mapped('')----------', direct_moves.mapped('picking_id'))
        upcoming_shipments = {}
        for line in ocean_moves:
            if line.purchase_line_id.order_id.end_loc_id.get_warehouse().id in upcoming_shipments:
                if upcoming_shipments[
                    line.purchase_line_id.order_id.end_loc_id.get_warehouse().id] > line.purchase_line_id.order_id.expected_final_transfer:
                    upcoming_shipments[
                        line.purchase_line_id.order_id.end_loc_id.get_warehouse().id] = line.purchase_line_id.order_id.expected_final_transfer
            else:
                upcoming_shipments[
                    line.purchase_line_id.order_id.end_loc_id.get_warehouse().id] = line.purchase_line_id.order_id.expected_final_transfer

        for line in direct_moves:
            if line.warehouse_id.id in upcoming_shipments:
                if upcoming_shipments[line.warehouse_id.id] > line.date:
                    upcoming_shipments[line.warehouse_id.id] = line.date
            else:
                upcoming_shipments[line.warehouse_id.id] = line.date
        # print('b-----------------', upcoming_shipments)
        return upcoming_shipments

    def find_set_delivery_line(self, carrier, price):
        if self.bigcommerce_store_id or self.channel_mapping_ids or self.is_amazon_order:
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
                    [('code', '=', 'package'), ('carrier_id', '=', shp_service.carrier_id.id)],
                    limit=1)
            self.write({
                'carrier_id': carrier.id,
                'is_shipstation_shipping': True,
                'shipstation_package_id': shp_package.id,
                'shipstation_service_id': shp_service and shp_service.id or False,
                'shipstation_carrier_id': shp_service and shp_service.carrier_id.id or False,
                'shipstation_account_id': carrier.shipstation_id.id,
            })
            self.set_delivery_line(carrier, price)
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

    # def pdct_dup(self):
    #     default_code = self.env['product.product'].with_context(active_test=False).search([('default_code', '!=', False)]).mapped('default_code')
    #     defaule_codes = list(set(list(default_code)))
    #     for each in defaule_codes:
    #         products = self.env['product.product'].with_context(active_test=False).search([('default_code', '=', each)])
    #         count = 1
    #         if len(products)>2:
    #             print(products[0].default_code)
    #         for pd in products:
    #             pd.write({'default_code': pd.default_code + str(count)})
    #             count += 1

    def max_qty_wh(self):
        product_id = self.order_line.mapped('product_id')[0]
        warehouses = self.env['stock.warehouse'].search(
            [('warehouse_type', '=', 'main_warehouse'), ('company_id', '=', self.company_id.id)])
        quantity = {}
        for warehouse_id in warehouses:
            qty = product_id.with_context(warehouse=warehouse_id.id).qty_available
            quantity[warehouse_id] = qty
        return quantity

    def update_warehouse(self, classification):
        warehouses = self.env['stock.warehouse'].search(
            [('warehouse_type', '=', 'main_warehouse'), ('company_id', '=', self.company_id.id)])
        if not warehouses:
            raise UserError(_('Please Define A Main Warehouse '))
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
        flat_calc = False
        price_dict = {}
        time_dict = {}
        product_id = self.order_line.mapped('product_id')[0]
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
        price_dict = {k: v for k, v in sorted(price_dict.items(), key=lambda item: item[1])}
        time_dict = {k: v for k, v in sorted(time_dict.items(), key=lambda item: item[1])}
        log = ''
        # print('price_dict', price_dict)
        # print('time_dict', time_dict)
        if product_id.is_flat_rate and product_id.delivery_carrier_id.fedex_service_type == fedex_service_type:
            flat_calc = True
            log += 'selecting Flat rate logic\n'
            self.message_post(body=('Product is on Flat Rate'),
                              subtype_id=self.env.ref('mail.mt_note').id)
        if not len(list(set(list(time_dict.values())))) == 1 and not flat_calc:
            log += 'selecting based on delivery time\n'
            warehouse, log = self.find_warehouse(time_dict, quantity, warehouses, log)
            if not warehouse:
                warehouse = min(time_dict, key=time_dict.get)
        elif not len(list(set(list(price_dict.values())))) == 1 and not flat_calc:
            log += 'selecting based on rate\n'
            warehouse, log = self.find_warehouse(price_dict, quantity, warehouses, log)
            if not warehouse:
                warehouse = min(price_dict, key=price_dict.get)
        else:
            log += 'selecting based on quantity\n'
            if not len(list(set(list(quantity.values())))) == 1 or list(set(list(quantity.values()))) != [0]:
                log += 'selecting based on max quantity\n'
                warehouse = max(quantity, key=quantity.get)
            if list(set(list(quantity.values()))) == [0]:
                warehouse, log = self.find_warehouse(price_dict, quantity, warehouses, log)
                if not warehouse:
                    warehouse = max(quantity, key=quantity.get)
        self.find_set_delivery_line(carrier, price_dict[warehouse])
        td = ''
        for wh in warehouses:
            td += '<tr><td style="color:#008080;text-align:center;padding:0 12px 0 12px;">%s</td><td style="color:#008080;text-align:center;padding:0 12px 0 12px;">%s</td><td style="color:#008080;text-align:center;padding:0 12px 0 12px;">%s</td><td style="color:#008080;text-align:center;padding:0 12px 0 12px;">%s</td></tr>' % (
                wh.name, (time_dict[wh]).strftime("%m/%d/%Y, %H:%M"), price_dict[wh],
                quantity[wh])

        th = '<thead><tr><th style="text-align:center;padding:0 12px 0 12px;">Warehouse</th><th style="text-align:center;padding:0 12px 0 12px;">Delivery Date</th><th style="text-align:center;padding:0 12px 0 12px;">Rate</th><th style="text-align:center;padding:0 12px 0 12px;">Qty Available</th></tr></thead>'

        self.message_post(
            body=('<h4>Warehouse Selection Info:- </h4><h6>Classification Type - %s</h6><table>%s%s</table>') % (
                address_type, th, td),
            subtype_id=self.env.ref('mail.mt_note').id)
        self.log_note = log
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
                quantity = order.max_qty_wh()
                warehouse = max(quantity, key=quantity.get)
                if warehouse:
                    order.warehouse_id = warehouse.id
            else:
                fedex_carrier = self.env['delivery.carrier'].search([('delivery_type', '=', 'fedex')], limit=1)
                classification = fedex_carrier.fedex_validate_address(partner=order.partner_shipping_id)
                warehouse = order.update_warehouse(classification)
                if warehouse:
                    order.warehouse_id = warehouse.id
        if order.bigcommerce_store_id or order.channel_mapping_ids or order.is_amazon_order:
            order.action_confirm()
        return order
