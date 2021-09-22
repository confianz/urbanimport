from odoo import fields, models, api
import base64
import json
from datetime import datetime
from requests import request
import time
import binascii
from odoo.exceptions import ValidationError
import sys
from threading import Thread
import logging
_logger = logging.getLogger("BigCommerce")
from dateutil.relativedelta import relativedelta

class SaleOrderVts(models.Model):
    _inherit = "sale.order"

    big_commerce_order_id = fields.Char(string="BigCommerce Order ID", readonly=True,copy=False)
    bigcommerce_store_id = fields.Many2one('bigcommerce.store.configuration', string="Bigcommerce Store", copy=False)
    bigcommerce_shipment_order_status = fields.Char(string='Bigcommerce Shipment Order Status',readonly=True)
    payment_status = fields.Selection([('paid', 'Paid'), ('not_paid', 'Not Paid')], string='Payment Status',
                                      default='not_paid')
    bigcommerce_shipment_address_id = fields.Char(string='Shipping Order Address ID')
    payment_method = fields.Char(string='Payment Method')

    def get_shipped_qty(self):
        bigcommerce_store_hash = self.bigcommerce_store_id.bigcommerce_store_hash
        bigcommerce_client_seceret  = self.bigcommerce_store_id.bigcommerce_x_auth_client
        bigcommerce_x_auth_token = self.bigcommerce_store_id.bigcommerce_x_auth_token
        headers = {"Accept": "application/json",
                   "X-Auth-Client": "{}".format(bigcommerce_client_seceret),
                   "X-Auth-Token": "{}".format(bigcommerce_x_auth_token),
                   "Content-Type": "application/json"}


        url = "%s%s/v2/orders/%s/products"%(self.bigcommerce_store_id.bigcommerce_api_url,bigcommerce_store_hash,self.big_commerce_order_id)
        try:
            response = request(method="GET",url=url,headers=headers)
            response = response.json()
            for response in response:
                product_ids = []
                domain = []
                bigcommerce_product_id = response.get('product_id')
                product_template_id = self.env['product.template'].search(
                    [('bigcommerce_product_id', '=', bigcommerce_product_id), (
                            'bigcommerce_store_id', '=', self.bigcommerce_store_id.id)])
                if response.get('product_options'):
                    for product_option in response.get('product_options'):
                        attribute_obj = self.env['product.attribute'].search([('bigcommerce_attribute_id','=',product_option.get('product_option_id'))])
                        value_obj = self.env['product.attribute.value'].search([('bigcommerce_value_id','=',int(product_option.get('value')))])
                        #attrib.append(attribute_obj.id)
                        #val_obj.append(value_obj.id)
                        template_attribute_obj = self.env['product.template.attribute.value'].search(
                            [('attribute_id', 'in', attribute_obj.ids), ('product_attribute_value_id', 'in', value_obj.ids),
                             ('product_tmpl_id', '=', product_template_id.id)])
                        #val_obj.append(template_attribute_obj)
                        domain = [('product_template_attribute_value_ids', 'in', template_attribute_obj.ids),('product_tmpl_id','=',product_template_id.id)]
                        if product_ids:
                            domain += [('id','in',product_ids)]
                        product_id = self.env['product.product'].search(domain)
                        product_ids += product_id.ids
                else:
                    product_id = self.env['product.product'].sudo().search([('product_tmpl_id','=',product_template_id.id)],limit=1)
                    #product_id = product_template_id.product_variant_id
                order_line = self.order_line.filtered(lambda line:line.product_id in product_id)
                order_line.quantity_shipped = response.get('quantity_shipped')
                self._cr.commit()
        except Exception as e:
            raise ValidationError(e)

    def create_sales_order_from_bigcommerce(self, vals):
        sale_order = self.env['sale.order']
        fpos = False
        order_vals = {
            'company_id': vals.get('company_id'),
            'partner_id': vals.get('partner_id'),
            'partner_invoice_id': vals.get('partner_invoice_id'),
            'partner_shipping_id': vals.get('partner_shipping_id'),
            'warehouse_id': vals.get('warehouse_id'),
        }
        new_record = sale_order.new(order_vals)
        new_record.onchange_partner_id()
        order_vals = sale_order._convert_to_write({name: new_record[name] for name in new_record._cache})
        new_record = sale_order.new(order_vals)
        new_record.with_context(force_company=vals.get('company_id')).onchange_partner_shipping_id()
        order_vals = sale_order._convert_to_write({name: new_record[name] for name in new_record._cache})
        fpos = order_vals.get('fiscal_position_id', fpos)
        if not fpos:
            fpos = self.env['account.fiscal.position'].with_context(force_company=vals.get('company_id')).get_fiscal_position(vals.get('partner_id'),vals.get('partner_id'))
        order_vals.update({
            'company_id': vals.get('company_id'),
            'picking_policy': 'direct',
            'partner_invoice_id': vals.get('partner_invoice_id'),
            'partner_shipping_id': vals.get('partner_shipping_id'),
            'partner_id': vals.get('partner_id'),
            'date_order': vals.get('date_order', ''),
            'state': 'draft',
            'carrier_id': vals.get('carrier_id', ''),
            'currency_id':vals.get('currency_id',False),
            'pricelist_id': vals.get('pricelist_id'),
            'note': vals.get('customer_message', ''),
            'fiscal_position_id': fpos
        })
        return order_vals

    def create_sale_order_line_from_bigcommerce(self, vals):
        sale_order_line = self.env['sale.order.line']
        order_line = {
            'order_id': vals.get('order_id'),
            'product_id': vals.get('product_id', ''),
            'company_id': vals.get('company_id', ''),
            'name': vals.get('description'),
            'product_uom': vals.get('product_uom')
        }
        new_order_line = sale_order_line.new(order_line)
        new_order_line.product_id_change()
        order_line = sale_order_line._convert_to_write({name: new_order_line[name] for name in new_order_line._cache})
        order_line.update({
            'order_id': vals.get('order_id'),
            'product_uom_qty': vals.get('order_qty', 0.0),
            'price_unit': vals.get('price_unit', 0.0),
            'discount': vals.get('discount', 0.0),
            'state': 'draft',
        })
        return order_line

    def create_bigcommerce_operation(self, operation, operation_type, bigcommerce_store_id, log_message, warehouse_id):
        vals = {
            'bigcommerce_operation': operation,
            'bigcommerce_operation_type': operation_type,
            'bigcommerce_store': bigcommerce_store_id and bigcommerce_store_id.id,
            'bigcommerce_message': log_message,
            'warehouse_id': warehouse_id and warehouse_id.id or False
        }
        operation_id = self.env['bigcommerce.operation'].create(vals)
        return operation_id

    def create_bigcommerce_operation_detail(self, operation, operation_type, req_data, response_data, operation_id,
                                            warehouse_id=False, fault_operation=False, process_message=False):
        bigcommerce_operation_details_obj = self.env['bigcommerce.operation.details']
        vals = {
            'bigcommerce_operation': operation,
            'bigcommerce_operation_type': operation_type,
            'bigcommerce_request_message': '{}'.format(req_data),
            'bigcommerce_response_message': '{}'.format(response_data),
            'operation_id': operation_id.id,
            'warehouse_id': warehouse_id and warehouse_id.id or False,
            'fault_operation': fault_operation,
            'process_message': process_message,
        }
        operation_detail_id = bigcommerce_operation_details_obj.create(vals)
        return operation_detail_id
    def bigcommerce_shipping_address_api_method(self, order=False, bigcommerce_store_id=False):
        """
        :return:  this method return shipping address of given order number
        :param order, bigcommerce_store_id
        """
        api_url = order.get('shipping_addresses').get('url')
        auth_token = bigcommerce_store_id and bigcommerce_store_id.bigcommerce_x_auth_token
        try:
            if api_url:
                headers = {"Accept": "application/json",
                           "X-Auth-Token": auth_token,
                           "Content-Type": "application/json"}
                response_data = request(method="GET", headers=headers, url=api_url)
                if response_data.status_code in [200, 201]:
                    _logger.info(">>>>> Get Successfully Response From {}".format(api_url))
                    response_data = response_data.json()
                    for data in response_data:
                        return data
            else:
                _logger.info(">>>>> api url not found in response ")
                return None
        except Exception as error:
            _logger.info(">>>>> Getting an Error {}".format(error))

    # def bigcommerce_to_odoo_import_orders(self,warehouse_id=False, bigcommerce_store_ids=False, last_modification_date =False, today_date=False, total_pages=20):
    def bigcommerce_to_odoo_import_orders(self,warehouse_id=False, bigcommerce_store_ids=False, last_modification_date =False, today_date=False, total_pages=2):
        for bigcommerce_store_id in bigcommerce_store_ids:
            req_data = False
            process_message = "Process Completed Successfully!"
            operation_id = self.create_bigcommerce_operation('order', 'import',bigcommerce_store_id, 'Processing...',warehouse_id)
            self._cr.commit()
            late_modification_date_flag = False
            today_date = datetime.now() + relativedelta(hours=5)
            try:
                last_modification_date = last_modification_date if last_modification_date else bigcommerce_store_id.from_order_date
                # print('last_modification_date',last_modification_date)
                last_date = last_modification_date.strftime("%Y-%m-%d")
                last_time = last_modification_date.strftime("%H:%M:%S")
                today_date = today_date if today_date else bigcommerce_store_id.last_modification_date
                diff =  today_date - last_modification_date
                total_pages = total_pages if total_pages else (diff.days * 2)
                todaydate = today_date.strftime("%Y-%m-%d")
                todaytime = today_date.strftime("%H:%M:%S")
                last_modification_date = last_date + " " + last_time
                today_date = todaydate + " " + todaytime
                for page_no in range(1,total_pages):
                    # api_operation = "/v2/orders?max_date_created={0}&min_date_created={1}&page={2}&limit={3}".format(today_date,last_modification_date,page_no,250)
                    api_operation = "/v2/orders?max_date_created={0}&min_date_created={1}&status_id={2}".format(today_date,last_modification_date,bigcommerce_store_id.bigcommerce_order_status or '11')
                    response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(api_operation)
                    if response_data.status_code in [200, 201]:
                        response_data = response_data.json()
                        _logger.info("Order Response Data : {0}".format(response_data))
                        for order in response_data:
                            order_id =None
                            if order.get('status') == 'Cancelled':
                                continue
                            big_commerce_order_id = order.get('id')
                            sale_order = self.env['sale.order'].search([('big_commerce_order_id', '=', big_commerce_order_id), (
                            'bigcommerce_store_id', '=', bigcommerce_store_id.id)])
                            if not sale_order:
                                shipping_address_api_respons = self.bigcommerce_shipping_address_api_method(order,bigcommerce_store_id)
                                date_time_str = order.get('orderDate')
                                customerEmail = order.get('billing_address').get('email')

                                city = order.get('billing_address').get('city')
                                first_name = order.get('billing_address').get('first_name')
                                last_name = order.get('billing_address').get('last_name')
                                country_iso2 = order.get('billing_address').get('country_iso2')
                                street = order.get('billing_address').get('street_1','')
                                street_2 = order.get('billing_address').get('street_2','')
                                country_obj = self.env['res.country'].search(
                                    [('code', '=', country_iso2)], limit=1)

                                phone = order.get('billing_address').get('phone')
                                zip = order.get('billing_address').get('zip')

                                total_tax= order.get('total_tax')
                                customerId = order.get('customer_id')
                                carrier_id  = self.env['delivery.carrier'].search([('is_bigcommerce_shipping_method','=',True)],limit=1)
                                partner_obj = self.env['res.partner'].search(
                                    [('bigcommerce_customer_id', '=', customerId), (
                                        'bigcommerce_store_id', '=', bigcommerce_store_id.id)], limit=1)
                                partner_vals = {
                                        'phone': phone,
                                        'zip':zip,
                                        'city':city,
                                        'country_id':country_obj and country_obj.id,
                                        'email': customerEmail,
                                        'is_available_in_bigcommerce': True,
                                        'bigcommerce_store_id': bigcommerce_store_id.id,
                                        'street':street,
                                        'street2':street_2
                                    }
                                if customerId==0:
                                    partner_vals.update({
                                        'name': "%s %s (Guest)" % (first_name, last_name),
                                        'bigcommerce_customer_id': "Guest User",
                                    })
                                    partner_obj = self.env['res.partner'].create(partner_vals)
                                if not partner_obj:
                                    partner_vals.update({
                                        'name': "%s %s" % (first_name, last_name),
                                        'bigcommerce_customer_id':customerId,
                                    })
                                    partner_obj = self.env['res.partner'].create(partner_vals)
                                if not partner_obj:
                                    process_message = "Customer is not exist in Odoo {}".format(customerId)
                                    self.create_bigcommerce_operation_detail('order', 'import', req_data, response_data,
                                                                             operation_id, warehouse_id, True,
                                                                             process_message)
                                    late_modification_date_flag=True
                                    continue
                                shipping_partner_state = shipping_address_api_respons.get('state') or ''  # change the state
                                shipping_partner_country = shipping_address_api_respons.get(
                                    'country') or ''  # chnage the country
                                state_id = self.env['res.country.state'].search([('name', '=', shipping_partner_state)],
                                                                                limit=1)
                                country_id = self.env['res.country'].search([('name', '=', shipping_partner_country)],
                                                                            limit=1)
                                # add address field heare
                                shipping_partner_first_name = shipping_address_api_respons.get('first_name')
                                shipping_partner_last_name = shipping_address_api_respons.get('last_name')
                                shipping_partner_company = shipping_address_api_respons.get('company')
                                shipping_partner_name = "%s %s" % (shipping_partner_first_name, shipping_partner_last_name)
                                shipping_partner_street_1 = shipping_address_api_respons.get('street_1')
                                shipping_partner_street_2 = shipping_address_api_respons.get('street_2')
                                shipping_partner_city = shipping_address_api_respons.get('city')
                                shipping_partner_zip = shipping_address_api_respons.get('zip')
                                shipping_partner_email = shipping_address_api_respons.get('email')
                                shipping_partner_phone = shipping_address_api_respons.get('phone')

                                partner_shipping_id = self.env['res.partner'].sudo().search(
                                    [('street', '=', shipping_partner_street_1), ('zip', '=', shipping_partner_zip),
                                     ('email', '=', shipping_partner_email), ('country_id', '=', country_id.id)], limit=1)

                                if not partner_shipping_id:
                                    _logger.info(">>> creating new partner ")
                                    res_partner_vals = {
                                        'name': shipping_partner_name,
                                        'bc_companyname': shipping_partner_company,
                                        'phone': shipping_partner_phone,
                                        'email': shipping_partner_email,
                                        'street': shipping_partner_street_1,
                                        'street2': shipping_partner_street_2,
                                        'city': shipping_partner_city,
                                        'zip': shipping_partner_zip,
                                        'state_id': state_id.id,
                                        'type': 'delivery',
                                        'parent_id': partner_obj.id,
                                        'country_id': country_id.id
                                    }
                                    partner_shipping_id = self.env['res.partner'].sudo().create(res_partner_vals)
                                    _logger.info(
                                        ">>> successfully create shipping partner {}".format(shipping_partner_first_name))
                                    self._cr.commit()
                                pricelist_id = self.env['product.pricelist'].search(
                                    [('currency_id.name', '=', order.get('currency_code'))], limit=1)
                                if not pricelist_id:
                                    pricelist_id = bigcommerce_store_id.pricelist_id
                                _logger.info(
                                    "Currency Code >>> {0} >>> Pricelist >>> {1}".format(order.get('currency_code'),
                                                                                         pricelist_id))
                                vals = {}
                                # vals = {
                                #     'name': order.get('billing_address').get('first_name'),
                                #     'street': order.get('billing_address').get('street_1'),
                                #     'street2': order.get('billing_address').get('street_2'),
                                #     'city': order.get('billing_address').get('city'),
                                #     'state_id': state_id and state_id.id or False,
                                #     'country_id': country_id and country_id.id or False,
                                #     'phone': order.get('billing_address').get('phone'),
                                #     'zip': order.get('billing_address').get('zip'),
                                #     'type': 'delivery',
                                #     'parent_id': partner_obj.id
                                # }

                                shipping_method = shipping_address_api_respons.get('shipping_method')
                                base_shipping_cost = shipping_address_api_respons.get('base_cost', 0.0)
                                currency_id = self.env['res.currency'].search([('name','=',order.get('currency_code'))],limit=1)

                                vals.update({
                                    'partner_id': partner_obj.id,
                                    'partner_invoice_id': partner_obj.id,
                                    'partner_shipping_id': partner_shipping_id.id,  # chnage value shipin_id
                                    'date_order': date_time_str or today_date,
                                    'bc_order_date': date_time_str or today_date,
                                    'carrier_id': carrier_id and carrier_id.id,
                                    'company_id': warehouse_id.company_id and warehouse_id.company_id.id or self.env.user.company_id.id,
                                    'warehouse_id': warehouse_id.id,
                                    'carrierCode': '',
                                    'serviceCode': '',
                                    'currency_id': currency_id.id,
                                    'delivery_price': base_shipping_cost,
                                    'pricelist_id': partner_obj.property_product_pricelist.id if partner_obj.property_product_pricelist else pricelist_id.id,
                                    'customer_message': order.get('customer_message', ''),
                                    'amount_tax': total_tax
                                })
                                order_vals = self.create_sales_order_from_bigcommerce(vals)
                                order_vals.update({'big_commerce_order_id': big_commerce_order_id,
                                                   'bigcommerce_store_id': bigcommerce_store_id.id,
                                                   'payment_status': 'paid' if order.get('payment_status') == "captured" else 'not_paid',
                                                   'payment_method': order.get('payment_method'),
                                                   'bigcommerce_shipment_order_status': order.get('status')
                                                   })
                                try:
                                    order_id = self.create(order_vals)
                                    if carrier_id and order_id:
                                        order_id.set_delivery_line(carrier_id, base_shipping_cost)
                                    discount_product_id = self.env.ref('bigcommerce_odoo_integration.product_product_bigcommerce_discount')
                                    self.env['sale.order.line'].sudo().create({'product_id':discount_product_id.id,'price_unit':-float(order.get('discount_amount')),'product_uom_qty':1.0,'state': 'draft','order_id':order_id.id,'company_id':order_id.company_id.id})
                                except Exception as e:
                                    process_message = "Getting an Error In Create Order procecss {}".format(e)
                                    self.create_bigcommerce_operation_detail('order', 'import', '', '', operation_id,
                                                                             warehouse_id, True, process_message)
                                    late_modification_date_flag = True
                                    continue
                                process_message = "Sale Order Created {0}".format(order_id and order_id.name)
                                _logger.info("Sale Order Created {0}".format(order_id and order_id.name))
                                order_id.message_post(body="Order Successfully Import From Bigcommerce")
                                self.create_bigcommerce_operation_detail('order', 'import', req_data, response_data,
                                                                         operation_id, warehouse_id, False,
                                                                         process_message)
                                try:
                                    product_details = "/v2{0}".format(order.get('products').get('resource'))
                                    response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(product_details)
                                    # print('response_dataresponse_data-----------------', response_data)

                                    if response_data.status_code in [200, 201, 204]:
                                        response_data = response_data.json()
                                        if response_data and order_id:
                                            self.prepare_sale_order_lines(order_id,response_data,operation_id,warehouse_id)
                                        else:
                                            product_message="Product Is not available in order : {0}!".format(order_id and order_id.name)
                                            self.create_bigcommerce_operation_detail('order', 'import', req_data, response_data,
                                                                                     operation_id, warehouse_id, True,
                                                                                     product_message)
                                        #order_id.action_confirm()
                                except Exception as e:
                                    _logger.info("Getting an Error In Import Order Line Response {}".format(e))
                                    process_message = "Getting an Error In Import Order Response {}".format(e,order_id and order_id.name)
                                    self.create_bigcommerce_operation_detail('order', 'import', '', '', operation_id,
                                                                             warehouse_id, True, process_message)
                            else:
                                process_message = "Order Already in Odoo {}".format(sale_order and sale_order.name)
                                self.create_bigcommerce_operation_detail('order', 'import', req_data, response_data,
                                                                         operation_id, warehouse_id, True,
                                                                         process_message)
                                self._cr.commit()
                            order_id and order_id.action_confirm()
                        if not late_modification_date_flag:
                            current_date = datetime.now()
                            bigcommerce_store_id.last_modification_date=current_date
            except Exception as e:
                _logger.info("Getting an Error In Import Order Response {}".format(e))
                process_message="Getting an Error In Import Order Response {}".format(e)
                self.create_bigcommerce_operation_detail('order','import','','',operation_id,warehouse_id,True,process_message)
            operation_id and operation_id.write({'bigcommerce_message': process_message})
            bigcommerce_store_ids.bigcommerce_operation_message = " Import Sale Order Process Complete "
            self._cr.commit()

    def bigcommerce_to_odoo_import_orders_from_webhook(self, bigcommerce_order_id, warehouse_id=False,
                                                       bigcommerce_store_id=False):
        req_data = False
        process_message = "Process Completed Successfully!"
        operation_id = self.with_user(1).create_bigcommerce_operation('order', 'import', bigcommerce_store_id,
                                                                      'Processing...', warehouse_id)
        self._cr.commit()
        order_response_pages = []
        try:
            today_date = datetime.now()
            todaydate = today_date.strftime("%Y-%m-%d")
            api_operation = "/v2/orders/{0}".format(bigcommerce_order_id)
            response_data = bigcommerce_store_id.with_user(1).send_get_request_from_odoo_to_bigcommerce(api_operation)
            if response_data.status_code in [200, 201]:
                order = response_data.json()
                _logger.info("Order Response Data : {0} Type : {1}".format(order, type(order)))
                big_commerce_order_id = bigcommerce_order_id
                sale_order = self.env['sale.order'].with_user(1).search(
                    [('big_commerce_order_id', '=', big_commerce_order_id), (
                            'bigcommerce_store_id', '=', bigcommerce_store_id.id)])
                if not sale_order:
                    shipping_address_api_respons = self.bigcommerce_shipping_address_api_method(order,
                                                                                                bigcommerce_store_id)
                    shipping_method = shipping_address_api_respons.get('shipping_method')
                    base_shipping_cost = shipping_address_api_respons.get('base_cost')
                    date_time_str = order.get('orderDate')
                    customerEmail = order.get('billing_address').get('email')

                    city = order.get('billing_address').get('city')
                    first_name = order.get('billing_address').get('first_name')
                    last_name = order.get('billing_address').get('last_name')
                    country_iso2 = order.get('billing_address').get('country_iso2')
                    country_obj = self.env['res.country'].search(
                        [('code', '=', country_iso2)], limit=1)

                    phone = order.get('billing_address').get('phone')
                    zip = order.get('billing_address').get('zip')

                    total_tax = order.get('total_tax')
                    customerId = order.get('customer_id')
                    carrier_id = self.env['delivery.carrier'].with_user(1).search(
                        [('is_bigcommerce_shipping_method', '=', True)], limit=1)
                    partner_obj = self.env['res.partner'].with_user(1).search(
                        [('bigcommerce_customer_id', '=', customerId), (
                            'bigcommerce_store_id', '=', bigcommerce_store_id.id)], limit=1)
                    partner_vals = {
                        'name': "%s %s" % (first_name, last_name),
                        'phone': phone,
                        'zip': zip,
                        'city': city,
                        'country_id': country_obj and country_obj.id,
                        'email': customerEmail,
                        'bigcommerce_customer_id': "Guest User",
                        'is_available_in_bigcommerce': True,
                        'bigcommerce_store_id': bigcommerce_store_id.id
                    }
                    if customerId == 0:
                        partner_vals.update({
                            'name': "%s %s (Guest)" % (first_name, last_name),
                        })
                    if not partner_obj:
                        partner_obj = self.env['res.partner'].with_user(1).create(partner_vals)
                    shipping_partner_state = shipping_address_api_respons.get('state') or ''  # change the state
                    shipping_partner_country = shipping_address_api_respons.get(
                        'country') or ''  # chnage the country
                    state_id = self.env['res.country.state'].search([('name', '=', shipping_partner_state)],
                                                                    limit=1)
                    country_id = self.env['res.country'].search([('name', '=', shipping_partner_country)],
                                                                limit=1)
                    # add address field heare
                    shipping_partner_first_name = shipping_address_api_respons.get('first_name')
                    shipping_partner_last_name = shipping_address_api_respons.get('last_name')
                    shipping_partner_company = shipping_address_api_respons.get('company')
                    shipping_partner_name = "%s %s" % (shipping_partner_first_name, shipping_partner_last_name)
                    shipping_partner_street_1 = shipping_address_api_respons.get('street_1')
                    shipping_partner_street_2 = shipping_address_api_respons.get('street_2')
                    shipping_partner_city = shipping_address_api_respons.get('city')
                    shipping_partner_zip = shipping_address_api_respons.get('zip')
                    shipping_partner_email = shipping_address_api_respons.get('email')
                    shipping_partner_phone = shipping_address_api_respons.get('phone')
                    # search partner according country zipcode , email , name, street1
                    partner_shipping_id = self.env['res.partner'].sudo().search(
                        [('street', '=', shipping_partner_street_1), ('zip', '=', shipping_partner_zip),
                         ('email', '=', shipping_partner_email), ('country_id', '=', country_id.id)], limit=1)
                    if not partner_shipping_id:
                        _logger.info(">>> creating new partner ")
                        res_partner_vals = {
                            'name': shipping_partner_name,
                            'bc_companyname': shipping_partner_company,
                            'phone': shipping_partner_phone,
                            'email': shipping_partner_email,
                            'street': shipping_partner_street_1,
                            'street2': shipping_partner_street_2,
                            'city': shipping_partner_city,
                            'zip': shipping_partner_zip,
                            'state_id': state_id.id,
                            'type': 'delivery',
                            'parent_id':partner_obj.id,
                            'country_id': country_id.id
                        }
                        partner_shipping_id = self.env['res.partner'].sudo().create(res_partner_vals)
                        _logger.info(">>> successfully create shipping partner {}".format(shipping_partner_first_name))
                        self._cr.commit()
                    pricelist_id = self.env['product.pricelist'].search(
                        [('currency_id.name', '=', order.get('currency_code'))], limit=1)
                    vals = {}
                    vals.update({'partner_id': partner_obj.parent_id.id if partner_obj.parent_id else partner_obj.id,
                                 'partner_invoice_id': partner_obj.id,
                                 'partner_shipping_id': partner_shipping_id.id,
                                 'date_order': date_time_str or today_date,
                                 'bc_order_date': date_time_str or today_date,
                                 'carrier_id': carrier_id and carrier_id.id,
                                 'company_id': warehouse_id.company_id and warehouse_id.company_id.id or self.env.user.company_id.id,
                                 'warehouse_id': warehouse_id.id,
                                 'carrierCode': '',
                                 'serviceCode': '',
                                 'delivery_price': base_shipping_cost,
                                 'amount_tax': total_tax,
                                 'customer_message': order.get('customer_message', ''),
                                 'pricelist_id': partner_obj.property_product_pricelist.id if partner_obj.property_product_pricelist else pricelist_id.id
                                 })
                    order_vals = self.with_user(1).create_sales_order_from_bigcommerce(vals)
                    order_vals.update({'big_commerce_order_id': big_commerce_order_id,
                                       'bigcommerce_store_id': bigcommerce_store_id.id,
                                       'payment_status': 'paid' if order.get('payment_status') == "captured" else 'not_paid',
                                       'payment_method': order.get('payment_method'),
                                       'bigcommerce_shipment_order_status': order.get('status')
                                       })
                    try:
                        order_id = self.with_user(1).create(order_vals)
                        if carrier_id and order_id:
                            order_id.with_user(1).set_delivery_line(carrier_id, base_shipping_cost)
                    except Exception as e:
                        process_message = "Getting an Error In Create Order procecss {}".format(e)
                        self.with_user(1).create_bigcommerce_operation_detail('order', 'import', '', '', operation_id,
                                                                              warehouse_id, True, process_message)
                    process_message = "Sale Order Created {0}".format(order_id and order_id.name)
                    _logger.info("Sale Order Created {0}".format(order_id and order_id.name))
                    order_id.message_post(body="Order Successfully Import From Bigcommerce")
                    self.with_user(1).create_bigcommerce_operation_detail('order', 'import', req_data, response_data,
                                                                          operation_id, warehouse_id, False,
                                                                          process_message)
                    try:
                        product_details = "/v2{0}".format(order.get('products').get('resource'))
                        response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(product_details)
                        if response_data.status_code in [200, 201, 204]:
                            response_data = response_data.json()
                            _logger.info("Sale Order Product {0}".format(response_data))
                            if response_data and order_id:
                                self.with_user(1).prepare_sale_order_lines(order_id, response_data, operation_id,
                                                                           warehouse_id)
                                order_id.sudo()._amount_all()
                            else:
                                product_message = "Product Is not available in order : {0}!".format(
                                    order_id and order_id.name)
                                self.with_user(1).create_bigcommerce_operation_detail('order', 'import', req_data,
                                                                                      response_data,
                                                                                      operation_id, warehouse_id, True,
                                                                                      product_message)
                    except Exception as e:
                        _logger.info("Getting an Error In Import Order Line Response {}".format(e))
                        process_message = "Getting an Error In Import Order Response {}".format(e,
                                                                                                order_id and order_id.name)
                        self.with_user(1).create_bigcommerce_operation_detail('order', 'import', '', '', operation_id,
                                                                              warehouse_id, True, process_message)
                else:
                    process_message = "Order Already in Odoo {}".format(sale_order and sale_order.name)
                    self.with_user(1).create_bigcommerce_operation_detail('order', 'import', req_data, response_data,
                                                                          operation_id, warehouse_id, True,
                                                                          process_message)
                    self._cr.commit()
            else:
                _logger.info("Getting an Error In Import Orders Response {}".format(response_data))
                response_data = response_data.content
                process_message = "Getting an Error In Import Orders Response".format(response_data)
                self.with_user(1).create_bigcommerce_operation_detail('order', 'import', req_data, response_data,
                                                                      operation_id, warehouse_id, True, process_message)
        except Exception as e:
            _logger.info("Getting an Error In Import Order Response {}".format(e))
            process_message = "Getting an Error In Import Order Response {}".format(e)
            self.with_user(1).create_bigcommerce_operation_detail('order', 'import', '', '', operation_id, warehouse_id,
                                                                  True, process_message)
        operation_id and operation_id.write({'bigcommerce_message': process_message})
    
    def prepare_sale_order_lines(self,order_id=False,product_details=False,operation_id=False,warehouse_id=False):
        for order_line in product_details:
            product_bigcommerce_id = order_line.get('product_id')
            product_id = self.env['product.product'].search([('bigcommerce_product_id', '=', product_bigcommerce_id), (
                                            'bigcommerce_store_id', '=', order_id.bigcommerce_store_id.id)],
                                                            limit=1)

            if product_id.bigcommerce_product_variant_id:
                product_id = self.env['product.product'].search([('bigcommerce_product_variant_id', '=', order_line.get('variant_id')), (
                                            'bigcommerce_store_id', '=', order_id.bigcommerce_store_id.id)],
                                                            limit=1)

            if not product_id:
                response_msg = "Sale Order : {0} Prouduct Not Found Product SKU And Name : {1}".format(order_id and order_id.name, product_bigcommerce_id)
                self.create_bigcommerce_operation_detail('order','import','','',operation_id,warehouse_id,True,response_msg)
                continue
            quantity = order_line.get('quantity')
            price = order_line.get('base_price')
            total_tax = order_line.get('total_tax')
            vals = {'product_id': product_id.id, 'price_unit': price, 'order_qty': quantity,
                    'order_id': order_id and order_id.id, 'description': product_bigcommerce_id,
                    'company_id': self.env.user.company_id.id,
                    'big_commerce_tax': total_tax}
            order_line = self.create_sale_order_line_from_bigcommerce(vals)
            order_line = self.env['sale.order.line'].create(order_line)
            if order_line:
                order_line.big_commerce_tax=total_tax
            _logger.info("Sale Order line Created".format(
                order_line and order_line.product_id and order_line.product_id.name))
            response_msg = "Sale Order line Created For Order  : {0}".format(order_id.name)
            self.create_bigcommerce_operation_detail('order','import','','',operation_id,warehouse_id,False,response_msg)
        self._cr.commit()

    # def exportordertobigcommerce(self):
    #     """
    #     This Method Is Used Export Order To BigCommerce
    #     :return: If Successfully Export Return OrderId
    #     """
    #     if not self.bigcommerce_store_id:
    #         raise ValidationError("Please Select Bigcommerce Store")
    #     bigcommerce_store_hash = self.bigcommerce_store_id.bigcommerce_store_hash
    #     api_url = "%s%s/v2/orders"%(self.bigcommerce_store_id.bigcommerce_api_url,bigcommerce_store_hash)
    #     bigcommerce_auth_token = self.bigcommerce_store_id.bigcommerce_x_auth_token
    #     bigcommerce_auth_client = self.bigcommerce_store_id.bigcommerce_x_auth_client
    #
    #     headers ={ 'Accept'       : 'application/json',
    #                'Content-Type' : 'application/json',
    #                'X-Auth-Token' : "{}".format(bigcommerce_auth_token),
    #                'X-Auth-Client':  "{}".format(bigcommerce_auth_client) }
    #     ls = []
    #     #  attribute_id = self.order_line.product_id.attribute_line_ids.attribute_id.bigcommerce_attribute_id
    #     for line in self.order_line:
    #         # variant_combination_ids = self.env['product.variant.combination'].search(
    #         #     [('product_product_id', '=', line.product_id.id)]).mapped('product_template_attribute_value_id')
    #         product_option = []
    #         if line.product_id.bigcommerce_product_variant_id and line.product_id.product_template_attribute_value_ids:
    #             #self._cr.execute("select product_template_attribute_value_id from product_variant_combination where product_product_id={}".format(line.product_id.id))
    #             #res = self._cr.fetchall()
    #             attribute_ids = line.product_id.product_template_attribute_value_ids
    #             for attribute in attribute_ids:
    #                 attribute_value_id = attribute.product_attribute_value_id.bigcommerce_value_id
    #                 attribute_id = attribute.attribute_id.bigcommerce_attribute_id
    #                 product_option.append({'id':attribute_id,"value":str(attribute_value_id)})
    #         data = {
    #             "product_id": int(line.product_id.bigcommerce_product_id),
    #             "quantity": line.product_uom_qty,
    #             "price_inc_tax" : line.price_total,
    #             "price_ex_tax": line.price_subtotal,
    #             "product_options" : product_option
    #         }
    #         ls.append(data)
    #
    #     request_data= {
    #         'status_id' : 1,
    #         'billing_address' :{
    #             "first_name" : "{}".format(self.partner_id and self.partner_id.name),
    #             "street_1" : "{}".format(self.partner_id and self.partner_id.street),
    #             "city" :"{}".format(self.partner_id and self.partner_id.city),
    #             "state": "{}".format(self.partner_id and self.partner_id.state_id.name),
    #             "zip" : "{}".format(self.partner_id and self.partner_id.zip),
    #             "country": "{}".format(self.partner_id and self.partner_id.country_id.name),
    #             "email" :"{}".format(self.partner_id and self.partner_id.email) },
    #         'products': ls }
    #     operation_id = self.create_bigcommerce_operation('order', 'export', self.bigcommerce_store_id, 'Processing...',
    #                                                      self.warehouse_id)
    #     print('request_data',request_data)
    #     self._cr.commit()
    #     try:
    #         response = request(method="POST",url=api_url,data=json.dumps(request_data),headers=headers)
    #         _logger.info("Sending Post Request To {}".format(api_url))
    #         response_data = response.json()
    #         req_data = False
    #         process_message = "Successfully Export Order {}".format(response_data)
    #         self.create_bigcommerce_operation_detail('order', 'export', req_data, response_data,
    #                                                  operation_id, self.warehouse_id, False,
    #                                                  process_message)
    #     except Exception as e:
    #         _logger.info("Export Order Response {}".format(response.content))
    #         raise ValidationError(e)
    #     if response.status_code not in [200,201]:
    #         raise ValidationError("Getting Some Error {}".format(response.content))
    #         process_message = "Getting Some Error {}".format(response.content)
    #         self.create_bigcommerce_operation_detail('order', 'export', req_data, response_data,
    #                                                  operation_id, self.warehouse_id, False,
    #                                                  process_message)
    #     response_data = response.json()
    #     if not response_data.get('id'):
    #         raise ValidationError("Order Id Not Found In Response")
    #         self.create_bigcommerce_operation_detail('order', 'export', req_data, response_data,
    #                                                  operation_id, self.warehouse_id, False,
    #                                                  process_message)
    #     self.big_commerce_order_id = response_data.get('id')
    #     self.message_post(body="Successfully Order Export To odoo")
    #     process_message = "Order Id Not Found"
    #
    #     return {
    #         'effect': {
    #             'fadeout': 'slow',
    #             'message': "Yeah! Successfully Export Order .",
    #             'img_url': '/web/static/src/img/smile.svg',
    #             'type': 'rainbow_man',
    #         }
    #     }

    def get_shipment_address_id(self):
        bigcommerce_store_hash = self.bigcommerce_store_id.bigcommerce_store_hash
        bigcommerce_client_seceret = self.bigcommerce_store_id.bigcommerce_x_auth_client
        bigcommerce_x_auth_token = self.bigcommerce_store_id.bigcommerce_x_auth_token
        headers = {"Accept": "application/json",
                   "X-Auth-Client": "{}".format(bigcommerce_client_seceret),
                   "X-Auth-Token": "{}".format(bigcommerce_x_auth_token),
                   "Content-Type": "application/json"}

        url = "%s%s/v2/orders/%s/shipping_addresses?limit=%s" % (
        self.bigcommerce_store_id.bigcommerce_api_url, bigcommerce_store_hash, self.big_commerce_order_id, 1)
        try:
            response = request(method="GET", url=url, headers=headers)
            if response.status_code in [200, 201]:
                response = response.json()
                _logger.info("BigCommerce Get Shipment  Response : {0}".format(response))
                for response in response:
                    self.bigcommerce_shipment_address_id = response.get('id')
            else:
                self.with_user(1).message_post(
                    body="Getting an Error in Import Shipment Address : {0}".format(response.content))
        except Exception as e:
            self.with_user(1).message_post(body="Getting an Error in Import Shipment Information : {0}".format(e))

    def get_order_product_id(self):
        bigcommerce_store_hash = self.bigcommerce_store_id.bigcommerce_store_hash
        bigcommerce_client_seceret = self.bigcommerce_store_id.bigcommerce_x_auth_client
        bigcommerce_x_auth_token = self.bigcommerce_store_id.bigcommerce_x_auth_token
        headers = {"Accept": "application/json",
                   "X-Auth-Client": "{}".format(bigcommerce_client_seceret),
                   "X-Auth-Token": "{}".format(bigcommerce_x_auth_token),
                   "Content-Type": "application/json"}

        url = "%s%s/v2/orders/%s/products" % (
        self.bigcommerce_store_id.bigcommerce_api_url, bigcommerce_store_hash, self.big_commerce_order_id)
        try:
            response = request(method="GET", url=url, headers=headers)
            if response.status_code in [200, 201]:
                response = response.json()
                _logger.info("BigCommerce Get Shipment  Response : {0}".format(response))
                for response in response:
                    line_id = self.env['sale.order.line'].search([('order_id', '=', self.id), ('product_id.bigcommerce_product_id', '=', response.get('product_id'))])
                    line_id.order_product_id = response.get('id')
            else:
                self.with_user(1).message_post(
                    body="Getting an Error in Export Shipment Address : {0}".format(response.content))
        except Exception as e:
            self.with_user(1).message_post(body="Getting an Error in Export Shipment Information : {0}".format(e))

class SaleOrderLineVts(models.Model):
    _inherit = "sale.order.line"

    quantity_shipped = fields.Float(string='Shipped Products',copy=False)
    #x_studio_manufacturer = fields.Many2one('bc.product.brand',string='Manufacturer')
    big_commerce_tax = fields.Float(string="BigCommerce Tax", copy=False)

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])) if line.order_id and not line.order_id.big_commerce_order_id else line.big_commerce_tax,
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })
            if self.env.context.get('import_file', False) and not self.env.user.user_has_groups('account.group_account_manager'):
                line.tax_id.invalidate_cache(['invoice_repartition_line_ids'], [line.tax_id.id])

