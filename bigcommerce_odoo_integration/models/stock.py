import time
from requests import request
from datetime import datetime
from odoo import models, api, fields, _
import logging
from odoo.exceptions import ValidationError
import json

_logger = logging.getLogger("BigCommerce")


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    bc_shipping_provider = fields.Char(string='Shipping Provider')
    bigcommerce_shimpment_id = fields.Char(string="Bigcommerce Shipment Numebr")

    def export_shipment_to_bigcommerce(self):
        if not self.sale_id.big_commerce_order_id:
            raise ValidationError("Order Not Exported in BC you can't Export Shipment")
        self.sale_id.get_shipment_address_id()
        time.sleep(2)
        self.sale_id.get_order_product_id()
        bigcommerce_store_hash = self.sale_id.bigcommerce_store_id.bigcommerce_store_hash
        api_url = "%s%s/v2/orders/%s/shipments" % (
            self.sale_id.bigcommerce_store_id.bigcommerce_api_url, bigcommerce_store_hash,
            self.sale_id.big_commerce_order_id)
        bigcommerce_auth_token = self.sale_id.bigcommerce_store_id.bigcommerce_x_auth_token
        bigcommerce_auth_client = self.sale_id.bigcommerce_store_id.bigcommerce_x_auth_client

        headers = {'Accept': 'application/json',
                   'Content-Type': 'application/json',
                   'X-Auth-Token': "{}".format(bigcommerce_auth_token),
                   'X-Auth-Client': "{}".format(bigcommerce_auth_client)}
        ls = []
        for line in self.move_lines.filtered(lambda mv: mv.quantity_done != 0.0):
            order_product_id = line.sale_line_id.order_product_id
            line_data = {
                "order_product_id": int(order_product_id),
                # "product_id": int(line.sale_line_id.product_id.bigcommerce_product_id),
                "quantity": line.quantity_done or 0.0,
            }
            _logger.info("Product Data {0}".format(line_data))
            ls.append(line_data)

        request_data = {
            'tracking_number': self.carrier_tracking_ref,
            'order_address_id': self.sale_id.bigcommerce_shipment_address_id,
            'shipping_provider': 'fedex',
            'tracking_carrier': 'fedex',
            'items': ls
        }
        operation_id = self.sale_id.create_bigcommerce_operation('shipment', 'export',
                                                                 self.sale_id.bigcommerce_store_id, 'Processing...',
                                                                 False)
        self._cr.commit()
        try:
            response = request(method="POST", url=api_url, data=json.dumps(request_data), headers=headers)
            _logger.info("Sending Post Request To {}".format(api_url))
            if response.status_code in [200, 201]:
                response_data = response.json()
                self.message_post(body="Shipment Created in Bigcommerce : {}".format(response_data.get('id')))
                process_message = "Shipment Created in Bigcommerce : {}".format(response_data.get('id'))
                self.sale_id.create_bigcommerce_operation_detail('order', 'export', False, response_data,
                                                                 operation_id, False, False,
                                                                 process_message)
                self.bigcommerce_shimpment_id = response_data.get('id')
            else:
                process_message = response.content
                self.sale_id.create_bigcommerce_operation_detail('order', 'export', request_data, False,
                                                                 operation_id, False, True,
                                                                 process_message)
        except Exception as e:
            _logger.info(" Getting an Issue in Export Shipment Response {}".format(response.content))
            raise ValidationError(e)
        return {
            'effect': {
                'fadeout': 'slow',
                'message': "Yeah! Successfully Export Order .",
                'img_url': '/web/static/src/img/smile.svg',
                'type': 'rainbow_man',
            }
        }

    # def _action_done(self):
    #     res = super(StockPicking, self)._action_done()
    #     customer_location_id = self.env.ref('stock.stock_location_customers')
    #     if self.location_dest_id.id == customer_location_id.id:
    #         self.export_shipment_to_bigcommerce()
    #     return res

    def get_order_shipment(self):
        tracking_number = shipping_provider = ''
        shipping_cost = 0.0
        bigcommerce_store_hash = self.sale_id.bigcommerce_store_id.bigcommerce_store_hash
        bigcommerce_client_seceret = self.sale_id.bigcommerce_store_id.bigcommerce_x_auth_client
        bigcommerce_x_auth_token = self.sale_id.bigcommerce_store_id.bigcommerce_x_auth_token
        headers = {"Accept": "application/json",
                   "X-Auth-Client": "{}".format(bigcommerce_client_seceret),
                   "X-Auth-Token": "{}".format(bigcommerce_x_auth_token),
                   "Content-Type": "application/json"}
        url = "%s%s/v2/orders/%s/shipments" % (
        self.sale_id.bigcommerce_store_id.bigcommerce_api_url, bigcommerce_store_hash,
        self.sale_id.big_commerce_order_id)
        try:
            response = request(method="GET", url=url, headers=headers)
            if response.status_code in [200, 201]:
                response = response.json()
                _logger.info("BigCommerce Get Shipment  Response : {0}".format(response))
                for response in response:
                    tracking_number += response.get('tracking_number')
                    shipping_provider += response.get('shipping_provider')
                    shipping_cost += float(response.get('merchant_shipping_cost'))
                    shipment_id = response.get('id')
                self.with_user(1).write({'carrier_price': shipping_cost, 'carrier_tracking_ref': tracking_number,
                                         'bc_shipping_provider': shipping_provider,
                                         'bigcommerce_shimpment_id': shipment_id})
                self.sale_id.with_user(1).bigcommerce_shipment_order_status = 'Shipped'
            else:
                self.with_user(1).message_post(
                    body="Getting an Error in Import Shipment Information : {0}".format(response.content))
        except Exception as e:
            self.with_user(1).message_post(body="Getting an Error in Import Shipment Information : {0}".format(e))


class StockInventory(models.Model):
    _inherit = 'stock.inventory'

    def create_and_update_inventory(self, inventory_dict, inventory_lines):
        """
        inventory_lines = [{'product_id': product1, 'location_id': location, 'product_qty': 10000},]
        inventory_dict = {
            'name': 'Test 57',
            'location_ids': 8
        }
        :param inventory_lines:
        :param inventory_dict:
        :return
        """
        inventory_val = {
            'name': inventory_dict.get('name'),
            'is_inventory_report': True,
            'location_ids': [(6, 0, [inventory_dict.get('location_ids')])],
            'date': time.strftime("%Y-%m-%d %H:%M:%S"),
            'company_id': self.company_id.id or self.env.user.company_id.id,
            'prefill_counted_quantity': 'zero',
        }
        _logger.info("::: creating inventory val {}".format(inventory_val))
        inventory_id = self.sudo().create(inventory_val)
        inventory_line_obj = self.env['stock.inventory.line']
        product_ids_ls = []
        if isinstance(inventory_lines, list):
            for inventory_line in inventory_lines:
                product_id = inventory_line.get('product_id') and inventory_line.get('product_id')
                inventory_line_val = {'product_id': product_id.id,
                                      'inventory_id': inventory_id and inventory_id.id,
                                      'location_id': inventory_line.get('location_id') and inventory_line.get(
                                          'location_id').id,
                                      'product_qty': inventory_line.get('product_qty'),
                                      'product_uom_id': product_id.uom_id.id,
                                      }
                _logger.info("::: creating inventory line val {}".format(inventory_line_val))
                product_ids_ls.append(product_id.id)
                inventory_line_obj.sudo().create(inventory_line_val)
        inventory_id.write({'product_ids': [(6, 0, product_ids_ls)]})
        inventory_id.action_start()
        inventory_id.action_validate()
        self._cr.commit()
        return True

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
            'process_message': process_message
        }
        operation_detail_id = bigcommerce_operation_details_obj.create(vals)
        return operation_detail_id

    def bigcommerce_to_odoo_import_inventory(self, warehouse_id=False, bigcommerce_store_ids=False):
        for bigcommerce_store_id in bigcommerce_store_ids:
            product_inventory_message = "Process Completed Successfully!"
            operation_id = self.create_bigcommerce_operation('stock', 'import', bigcommerce_store_id, 'Processing...',
                                                             warehouse_id)
            self._cr.commit()
            try:
                product_ids = self.env['product.product'].search([('bigcommerce_product_id', '!=', False), (
                    'bigcommerce_store_id', '=', bigcommerce_store_id.id), ('is_exported_to_bigcommerce', '=', True)])
                # product_ids = self.env['product.product'].search([('bigcommerce_product_id','=',1146)])
                inventroy_line_obj = self.env['stock.inventory.line']
                inventory_name = "BigCommerce_Inventory_%s" % (str(datetime.now().date()))
                inventory_vals = {
                    'name': inventory_name,
                    #      'is_inventory_report': True,
                    'location_ids': [(6, 0, warehouse_id.lot_stock_id.ids)],
                    'date': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'company_id': warehouse_id.company_id and warehouse_id.company_id.id or False,
                    'filter': 'partial'
                }
                inventory_id = self.create(inventory_vals)
                for product_id in product_ids:
                    try:
                        if product_id.bigcommerce_product_variant_id:
                            api_operation = "/v3/catalog/products/%s/variants/%s" % (
                            product_id.bigcommerce_product_id, product_id.bigcommerce_product_variant_id)
                            response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(
                                api_operation)
                            _logger.info("BigCommerce Get Product  Response : {0}".format(response_data))

                            if response_data.status_code in [200, 201]:
                                response_data = response_data.json()
                                _logger.info("Inventory Response Data : {0}".format(response_data))
                                records = response_data.get('data')
                                available_quantity = records.get('inventory_level')
                                inventory_line = inventroy_line_obj.create({'product_id': product_id.id,
                                                                            'inventory_id': inventory_id and inventory_id.id,
                                                                            'location_id': warehouse_id.lot_stock_id.id,
                                                                            'product_qty': available_quantity,
                                                                            'product_uom_id': product_id.uom_id and product_id.uom_id.id,
                                                                            })
                                inventory_process_message = "%s : Product Inventory Imported!" % (product_id.name)
                                self.create_bigcommerce_operation_detail('stock', 'import', response_data,
                                                                         api_operation, operation_id,
                                                                         warehouse_id, False, inventory_process_message)
                            else:
                                process_message = "%s : Getting an Error In Import Product Responase : {0}".format(
                                    response_data)
                                _logger.info("Getting an Error In Import Product Responase".format(response_data))
                                self.create_bigcommerce_operation_detail('stock', 'import', response_data,
                                                                         api_operation, operation_id,
                                                                         warehouse_id, True, process_message)
                        else:
                            api_operation = "/v3/catalog/products/%s" % (product_id.bigcommerce_product_id)
                            response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(
                                api_operation)
                            _logger.info("BigCommerce Get Product  Response : {0}".format(response_data))
                            if response_data.status_code in [200, 201]:
                                response_data = response_data.json()
                                _logger.info("Inventory Response Data : {0}".format(response_data))
                                records = response_data.get('data')
                                available_quantity = records.get('inventory_level')
                                inventory_line = inventroy_line_obj.create({'product_id': product_id.id,
                                                                            'inventory_id': inventory_id and inventory_id.id,
                                                                            'location_id': warehouse_id.lot_stock_id.id,
                                                                            'product_qty': available_quantity,
                                                                            'product_uom_id': product_id.uom_id and product_id.uom_id.id,
                                                                            })
                                inventory_process_message = "%s : Product Inventory Imported!" % (
                                    product_id.name)
                                self.create_bigcommerce_operation_detail('stock', 'import', response_data,
                                                                         api_operation, operation_id,
                                                                         warehouse_id, False,
                                                                         inventory_process_message)
                                self._cr.commit()
                            else:
                                process_message = "%s : Getting an Error In Import Product Responase : {0}".format(
                                    response_data)
                                _logger.info(
                                    "Getting an Error In Import Product Responase".format(response_data))
                                self.create_bigcommerce_operation_detail('stock', 'import', response_data,
                                                                         api_operation, operation_id,
                                                                         warehouse_id, True, process_message)

                        self._cr.commit()
                    except Exception as e:
                        product_process_message = "%s : Process Is Not Completed Yet! %s" % (product_id.name, e)
                        _logger.info("Getting an Error In Import Product Responase".format(e))
                        self.create_bigcommerce_operation_detail('stock', 'import', "",
                                                                 "", operation_id,
                                                                 warehouse_id, True, product_process_message)
                inventory_id.action_start()
                inventory_id.action_validate()
                self._cr.commit()
            except Exception as e:
                product_process_message = "Process Is Not Completed Yet! %s" % (e)
                _logger.info("Getting an Error In Import Product Responase".format(e))
                self.create_bigcommerce_operation_detail('product', 'import', "", "",
                                                         operation_id, warehouse_id, True, product_process_message)
            operation_id and operation_id.write({'bigcommerce_message': product_inventory_message})
            self._cr.commit()

    @api.model
    def bigcommerce_to_odoo_import_inventory_using_cronjob(self):
        warehouse_ids = self.env['stock.warehouse'].search([])
        for warehouse_id in warehouse_ids:
            if warehouse_id.bigcommerce_store_ids:
                self.bigcommerce_to_odoo_import_inventory(warehouse_id, warehouse_id.bigcommerce_store_ids)
        return True
