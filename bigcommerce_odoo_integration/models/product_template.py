from odoo import fields, models, api
from requests import request
import logging
import json
import requests
import json
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
from datetime import datetime
import time
import base64
from odoo.exceptions import UserError, ValidationError
from odoo.addons.product.models.product import ProductProduct

_logger = logging.getLogger("BigCommerce")


class ProductProduct(models.Model):
    _inherit = "product.product"

    bigcommerce_product_variant_id = fields.Char(string='Bigcommerce Product Variant ID')
    bc_sale_price = fields.Float(string='BC Sale Price')


@api.depends('list_price', 'price_extra', 'bc_sale_price')
@api.depends_context('uom')
def _compute_product_lst_price(self):
    to_uom = None
    if 'uom' in self._context:
        to_uom = self.env['uom.uom'].browse(self._context['uom'])

    for product in self:
        if to_uom:
            list_price = product.uom_id._compute_price(product.list_price, to_uom)
        else:
            list_price = product.list_price
        product.lst_price = product.bc_sale_price


ProductProduct._compute_product_lst_price = _compute_product_lst_price


class ProductTemplate(models.Model):
    _inherit = "product.template"

    bigcommerce_product_image_ids = fields.One2many('bigcommerce.product.image', 'product_template_id',
                                                    string="Bigcommerce Product Image Ids")
    bigcommerce_product_id = fields.Char(string='Bigcommerce Product', copy=False)
    bigcommerce_store_id = fields.Many2one('bigcommerce.store.configuration', string="Bigcommerce Store", copy=False)
    is_exported_to_bigcommerce = fields.Boolean(string="Is Exported to Big Commerce ?", copy=False)
    inventory_tracking = fields.Selection([
        ('none', 'Inventory Level will not be tracked'),
        ('product', 'Inventory Level Tracked using the Inventory Level'),
        ('variant', 'Inventory Level Tracked Based on variant')
    ], default="none")
    inventory_warning_level = fields.Integer(string="Inventory Warning Level", copy=False)
    is_visible = fields.Boolean(string="Product Should Be Visible to Customer", default=True, copy=False)
    warranty = fields.Char(string="Warranty Information")
    is_imported_from_bigcommerce = fields.Boolean(string="Is Imported From Big Commerce ?", copy=False)
    x_studio_manufacturer = fields.Many2one('bc.product.brand', string='Manufacturer')
    bc_product_image_id = fields.Char(string='BC Product Image', copy=False)

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

    def product_request_data(self, product_id, warehouse_id):
        """
        Description : Prepare Product Request Data For Generate/Create Product in Bigcomeerce
        """
        product_variants = []
        product_name = product_id and product_id.name
        product_data = {
            "name": product_id.name,
            "price": product_id.list_price,
            "categories": [int(product_id.categ_id and product_id.categ_id.bigcommerce_product_category_id)],
            "weight": product_id.weight or 1.0,
            "type": "physical",
            "sku": product_id.default_code or '',
            "description": product_id.name,
            "cost_price": product_id.standard_price,
            "inventory_tracking": product_id.inventory_tracking,
            "inventory_level": product_id.with_context(warehouse=warehouse_id.id).qty_available,
            "is_visible": product_id.is_visible,
            "warranty": product_id.warranty or ''
        }
        return product_data

    def product_variant_request_data(self, product_variant):
        """
        Description : Prepare Product Variant Request Data For Create Product  Variant in Bigcommerce.
        """
        option_values = []
        product_data = {
            "cost_price": product_variant.standard_price,
            "price": product_variant.lst_price,
            "weight": product_variant.weight or 1.0,
            "sku": product_variant.default_code or '',
            "product_id": product_variant.product_tmpl_id.bigcommerce_product_id

        }
        for attribute_value in product_variant.attribute_value_ids:
            option_values.append({'id': attribute_value.bigcommerce_value_id,
                                  'option_id': attribute_value.attribute_id.bigcommerce_attribute_id})
        product_data.update({"option_values": option_values})
        return product_data

    def create_product_template(self, record, store_id):
        product_attribute_obj = self.env['product.attribute']
        product_attribute_value_obj = self.env['product.attribute.value']
        product_template_obj = self.env['product.template']
        template_title = ''
        if record.get('name', ''):
            template_title = record.get('name')
        attrib_line_vals = []
        _logger.info("{}".format(record.get('categories')))
        if record.get('variants'):
            for attrib in record.get('variants'):
                if not attrib.get('option_values'):
                    continue
                attrib_name = attrib.get('option_display_name')
                attrib_values = attrib.get('label')
                attribute = product_attribute_obj.get_product_attribute(attrib_name, type='radio',
                                                                        create_variant='always')
                attribute_val_ids = []

                attrib_value = product_attribute_value_obj.get_product_attribute_values(attrib_values, attribute.id)
                attribute_val_ids.append(attrib_value.id)

                if attribute_val_ids:
                    attribute_line_ids_data = [0, False, {'attribute_id': attribute.id,
                                                          'value_ids': [[6, False, attribute_val_ids]]}]
                    attrib_line_vals.append(attribute_line_ids_data)
        category_id = self.env['product.category'].sudo().search(
            [('bigcommerce_product_category_id', 'in', record.get('categories')),
             ('bigcommerce_store_id', '=', store_id.id)], limit=1)
        # category_id = self.env.ref('product.product_category_all')
        if not category_id:
            message = "Category not found!"
            _logger.info("Category not found: {}".format(category_id))
            return False, message
        # public_category_ids = self.env['product.public.category'].sudo().search([('bigcommerce_product_category_id', 'in', record.get('categories'))])
        brand_id = self.env['bc.product.brand'].sudo().search([('bc_brand_id', '=', record.get('brand_id')), (
            'bigcommerce_store_id', '=', store_id.id)], limit=1)
        _logger.info("BRAND : {0}".format(brand_id))
        vals = {
            'name': template_title,
            'type': 'product',
            'categ_id': category_id and category_id.id,
            "weight": record.get("weight"),
            "list_price": record.get("price"),
            "is_visible": record.get("is_visible"),
            # "public_categ_ids": [(6, 0, public_category_ids.ids)],
            "bigcommerce_product_id": record.get('id'),
            "bigcommerce_store_id": store_id.id,
            "default_code": record.get("sku"),
            "is_imported_from_bigcommerce": True,
            "x_studio_manufacturer": brand_id and brand_id.id,
            "description_sale": record.get('description')
        }
        product_template = product_template_obj.with_user(1).create(vals)
        _logger.info("Product Created: {}".format(product_template))
        return True, product_template

    def import_product_from_bigcommerce(self, warehouse_id=False, bigcommerce_store_ids=False):
        for bigcommerce_store_id in bigcommerce_store_ids:
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Auth-Client': '{}'.format(bigcommerce_store_ids.bigcommerce_x_auth_client),
                'X-Auth-Token': "{}".format(bigcommerce_store_ids.bigcommerce_x_auth_token)
            }
            req_data = False
            bigcommerce_store_id.bigcommerce_product_import_status = "Import Product Process Running..."
            product_process_message = "Process Completed Successfully!"
            operation_id = self.with_user(1).create_bigcommerce_operation('product', 'import', bigcommerce_store_id,
                                                                          'Processing...', warehouse_id)
            self._cr.commit()
            product_response_pages = []
            try:
                api_operation = "/v3/catalog/products"
                response_data = bigcommerce_store_id.with_user(1).send_get_request_from_odoo_to_bigcommerce(
                    api_operation)
                # _logger.info("BigCommerce Get Product  Response : {0}".format(response_data))
                product_ids = self.with_user(1).search([('bigcommerce_product_id', '=', False)])
                _logger.info("Response Status: {0}".format(response_data.status_code))
                if response_data.status_code in [200, 201]:
                    response_data = response_data.json()
                    # _logger.info("Product Response Data : {0}".format(response_data))
                    records = response_data.get('data')
                    location_id = bigcommerce_store_id.warehouse_id.lot_stock_id
                    total_pages = response_data.get('meta').get('pagination').get('total_pages')

                    to_page = bigcommerce_store_id.source_of_import_data
                    total_pages = bigcommerce_store_id.destination_of_import_data

                    if total_pages > 1:
                        while (total_pages >= to_page):
                            try:
                                page_api = "/v3/catalog/products?page=%s" % (total_pages)
                                page_response_data = bigcommerce_store_id.send_get_request_from_odoo_to_bigcommerce(
                                    page_api)
                                # _logger.info("Response Status: {0}".format(page_response_data.status_code))
                                if page_response_data.status_code in [200, 201]:
                                    page_response_data = page_response_data.json()
                                    _logger.info("Product Response Data : {0}".format(page_response_data))
                                    records = page_response_data.get('data')
                                    product_response_pages.append(records)
                            except Exception as e:
                                product_process_message = "Page is not imported! %s" % (e)
                                _logger.info("Getting an Error In Import Product Category Response {}".format(e))
                                process_message = "Getting an Error In Import Product Category Response {}".format(e)
                                self.with_user(1).create_bigcommerce_operation_detail('product', 'import',
                                                                                      response_data,
                                                                                      process_message, operation_id,
                                                                                      warehouse_id, True,
                                                                                      product_process_message)

                            total_pages = total_pages - 1
                    else:
                        product_response_pages.append(records)
                    location = location_id.ids + location_id.child_ids.ids
                    inventory_val = {
                        'name': "BC Import Product Inventory:{}".format(fields.Date.today()),
                        'location_ids': [(6, 0, location)],
                        'date': time.strftime("%Y-%m-%d %H:%M:%S"),
                        'company_id': self.company_id.id or self.env.user.company_id.id,
                        'prefill_counted_quantity': 'zero',
                    }
                    _logger.info("::: creating inventory val {}".format(inventory_val))
                    inventory_id = self.env['stock.inventory'].sudo().create(inventory_val)
                    product_ids_ls = []
                    inventory_line_obj = self.env['stock.inventory.line']
                    lot_stock_id = bigcommerce_store_id.warehouse_id.lot_stock_id
                    for product_response_page in product_response_pages:
                        for record in product_response_page:
                            try:
                                if bigcommerce_store_id.bigcommerce_product_skucode and record.get('sku'):
                                    product_template_id = self.env['product.template'].sudo().search(
                                        [('default_code', '=', record.get('sku')), (
                                            'bigcommerce_store_id', '=', bigcommerce_store_id.id)], limit=1)
                                else:
                                    product_template_id = self.env['product.template'].sudo().search(
                                        [('bigcommerce_product_id', '=', record.get('id')), (
                                            'bigcommerce_store_id', '=', bigcommerce_store_id.id)], limit=1)
                                if not product_template_id:
                                    status, product_template_id = self.with_user(1).create_product_template(record,
                                                                                                            bigcommerce_store_id)
                                    if not status:
                                        product_process_message = "%s : Product is not imported Yet! %s" % (
                                            record.get('id'), product_template_id)
                                        _logger.info("Getting an Error In Import Product Responase :{}".format(
                                            product_template_id))
                                        self.with_user(1).create_bigcommerce_operation_detail('product', 'import', "",
                                                                                              "", operation_id,
                                                                                              warehouse_id, True,
                                                                                              product_process_message)
                                        continue
                                    process_message = "Product Created : {}".format(product_template_id.name)
                                    _logger.info("{0}".format(process_message))
                                    response_data = record
                                    self.with_user(1).create_bigcommerce_operation_detail('product', 'import', req_data,
                                                                                          response_data, operation_id,
                                                                                          warehouse_id, False,
                                                                                          process_message)
                                    self._cr.commit()
                                else:
                                    process_message = "{0} : Product Already Exist In Odoo!".format(
                                        product_template_id.name)
                                    brand_id = self.env['bc.product.brand'].sudo().search(
                                        [('bc_brand_id', '=', record.get('brand_id')), (
                                            'bigcommerce_store_id', '=', bigcommerce_store_id.id)], limit=1)
                                    _logger.info("BRAND : {0}".format(brand_id))
                                    product_template_id.write({
                                        "list_price": record.get("price"),
                                        "is_visible": record.get("is_visible"),
                                        "bigcommerce_product_id": record.get('id'),
                                        "bigcommerce_store_id": bigcommerce_store_id.id,
                                        "default_code": record.get("sku"),
                                        "is_imported_from_bigcommerce": True,
                                        "is_exported_to_bigcommerce": True,
                                        "x_studio_manufacturer": brand_id and brand_id.id,
                                        "name": record.get('name')
                                    })
                                    self.with_user(1).create_bigcommerce_operation_detail('product', 'import', req_data,
                                                                                          response_data, operation_id,
                                                                                          warehouse_id, False,
                                                                                          process_message)
                                    _logger.info("{0}".format(process_message))
                                    self._cr.commit()
                                self.env['product.attribute'].import_product_attribute_from_bigcommerce(warehouse_id,
                                                                                                        bigcommerce_store_id,
                                                                                                        product_template_id,
                                                                                                        operation_id)
                                self.env['bigcommerce.product.image'].with_user(1).import_multiple_product_image(
                                    bigcommerce_store_id, product_template_id)
                                if product_template_id.product_variant_count > 1:
                                    api_operation_variant = "/v3/catalog/products/{}/variants".format(
                                        product_template_id.bigcommerce_product_id)
                                    variant_response_data = bigcommerce_store_id.with_user(
                                        1).send_get_request_from_odoo_to_bigcommerce(api_operation_variant)
                                    _logger.info(
                                        "BigCommerce Get Product Variant Response : {0}".format(variant_response_data))
                                    _logger.info(
                                        "Response Status: {0}".format(variant_response_data.status_code))
                                    if variant_response_data.status_code in [200, 201]:
                                        api_operation_variant_response_data = variant_response_data.json()
                                        variant_datas = api_operation_variant_response_data.get('data')
                                        for variant_data in variant_datas:
                                            option_labales = []
                                            option_values = variant_data.get('option_values')
                                            for option_value in option_values:
                                                option_labales.append(option_value.get('label'))
                                            v_id = variant_data.get('id')
                                            product_sku = variant_data.get('sku')
                                            _logger.info("Total Product Variant : {0} Option Label : {1}".format(
                                                product_template_id.product_variant_ids, option_labales))
                                            for product_variant_id in product_template_id.product_variant_ids:
                                                if product_variant_id.mapped(lambda pv: pv.with_user(
                                                        1).product_template_attribute_value_ids.mapped(
                                                    'name') == option_labales)[0]:
                                                    _logger.info(
                                                        "Inside If Condition option Label =====> {0} Product Template "
                                                        "Attribute Value ====> {1} variant_id====>{2}".format(
                                                            option_labales, product_variant_id.with_user(1).mapped(
                                                                'product_template_attribute_value_ids').mapped('name'),
                                                            product_variant_id))
                                                    if variant_data.get('price'):
                                                        price = variant_data.get('price')
                                                    else:
                                                        price = variant_data.get('calculated_price')
                                                    vals = {'default_code': product_sku, 'bc_sale_price': price,
                                                            'bigcommerce_product_variant_id': v_id,
                                                            'standard_price': variant_data.get('cost_price', 0.0)}
                                                    variant_product_img_url = variant_data.get('image_url')
                                                    if variant_product_img_url:
                                                        image = base64.b64encode(
                                                            requests.get(variant_product_img_url).content)
                                                        vals.update({'image_1920': image})
                                                    product_variant_id.with_user(1).write(vals)
                                                    _logger.info("Product Variant Updated : {0}".format(
                                                        product_variant_id.default_code))
                                                    self._cr.commit()
                                                    product_qty = variant_data.get('inventory_level')
                                                    if product_qty > 0:
                                                        inventory_line_val = {'product_id': product_variant_id.id,
                                                                              'inventory_id': inventory_id and inventory_id.id,
                                                                              'location_id': lot_stock_id.id,
                                                                              'product_qty': record.get(
                                                                                  'inventory_level'),
                                                                              'product_uom_id': product_variant_id.uom_id.id,
                                                                              }
                                                        _logger.info("::: creating inventory line val {}".format(
                                                            inventory_line_val))
                                                        product_ids_ls.append(product_variant_id.id)
                                                        inventory_line_obj.sudo().create(inventory_line_val)
                                    else:
                                        api_operation_variant_response_data = variant_response_data.json()
                                        error_msg = api_operation_variant_response_data.get('errors')
                                        self.create_bigcommerce_operation_detail('product_attribute', 'import', '',
                                                                                 error_msg, operation_id, warehouse_id,
                                                                                 True, error_msg)
                                else:
                                    product_id = self.env['product.product'].sudo().search(
                                        [('product_tmpl_id', '=', product_template_id.id)], limit=1)
                                    inventory_line_val = {'product_id': product_id.id,
                                                          'inventory_id': inventory_id and inventory_id.id,
                                                          'location_id': lot_stock_id.id,
                                                          'product_qty': record.get('inventory_level'),
                                                          'product_uom_id': product_id.uom_id.id,
                                                          }
                                    _logger.info("::: creating inventory line val {}".format(inventory_line_val))
                                    product_ids_ls.append(product_id.id)
                                    inventory_line_obj.sudo().create(inventory_line_val)
                                # location = location_id.ids + location_id.child_ids.ids
                                # quant_id = self.env['stock.quant'].with_user(1).search([('product_tmpl_id','=',product_template_id.id),('location_id','in',location)])
                                # if len(quant_id) > 1:
                                #     stock_quant_id = self.env['stock.quant'].with_user(1).search([('product_tmpl_id','=',product_template_id.id),('location_id','=',location_id.id)])
                                #     _logger.info(" Stock Quant : {0}".format(stock_quant_id))
                                #     stock_quant_id.with_user(1).unlink()
                                # quant_id = self.env['stock.quant'].with_user(1).search([('product_tmpl_id','=',product_template_id.id),('location_id','in',location)])
                                # if not quant_id:
                                #     product_id = self.env['product.product'].sudo().search([('product_tmpl_id','=',product_template_id.id)],limit=1)
                                #     vals = {'product_tmpl_id':product_template_id.id,'location_id':location_id.id,'inventory_quantity':record.get('inventory_level'),'product_id':product_id.id,'quantity':record.get('inventory_level')}
                                #     self.env['stock.quant'].sudo().create(vals)
                                # else:
                                #     quant_id.sudo().write({'inventory_quantity':record.get('inventory_level'),'quantity':record.get('inventory_level')})
                                self._cr.commit()
                            except Exception as e:
                                product_process_message = "%s : Product is not imported Yet! %s" % (record.get('id'), e)
                                _logger.info("Getting an Error In Import Product Responase".format(e))
                                self.with_user(1).create_bigcommerce_operation_detail('product', 'import', "",
                                                                                      "", operation_id,
                                                                                      warehouse_id, True,
                                                                                      product_process_message)

                    inventory_id.write({'product_ids': [(6, 0, product_ids_ls)]})
                    inventory_id.action_start()
                    inventory_id.action_validate()
                    _logger.info("Inventory Validated : {}".format(inventory_id.name))
                    operation_id and operation_id.with_user(1).write({'bigcommerce_message': product_process_message})
                    _logger.info("Import Product Process Completed ")
                else:
                    process_message = "Getting an Error In Import Product Responase : {0}".format(response_data)
                    _logger.info("Getting an Error In Import Product Responase".format(response_data))
                    self.with_user(1).create_bigcommerce_operation_detail('product', 'import', req_data, response_data,
                                                                          operation_id, warehouse_id, True, )
            except Exception as e:
                product_process_message = "Process Is Not Completed Yet! %s" % (e)
                _logger.info("Getting an Error In Import Product Responase".format(e))
                self.with_user(1).create_bigcommerce_operation_detail('product', 'import', "", "", operation_id,
                                                                      warehouse_id, True, product_process_message)
            bigcommerce_store_id.bigcommerce_product_import_status = "Import Product Process Completed."
            # product_process_message = product_process_message + "From :" + to_page +"To :" + total_pages
            operation_id and operation_id.with_user(1).write({'bigcommerce_message': product_process_message})
            self._cr.commit()

    def import_product_manually_from_bigcommerce(self, warehouse_id=False, bigcommerce_store_id=False,
                                                 product_id=False):
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Auth-Client': '{}'.format(bigcommerce_store_id.bigcommerce_x_auth_client),
            'X-Auth-Token': "{}".format(bigcommerce_store_id.bigcommerce_x_auth_token)
        }
        req_data = False
        product_process_message = "Process Completed Successfully!"
        self._cr.commit()
        product_response_pages = []
        try:
            location_id = bigcommerce_store_id.warehouse_id.lot_stock_id
            api_operation = "/v3/catalog/products/{}".format(product_id)
            location = location_id.ids + location_id.child_ids.ids
            response_data = bigcommerce_store_id.with_user(1).send_get_request_from_odoo_to_bigcommerce(api_operation)
            _logger.info("Response Status: {0}".format(response_data.status_code))
            inventory_val = {
                'name': "BC Import Product Inventory:{}".format(fields.Date.today()),
                'location_ids': [(6, 0, location)],
                'date': time.strftime("%Y-%m-%d %H:%M:%S"),
                'company_id': self.company_id.id or self.env.user.company_id.id,
                'prefill_counted_quantity': 'zero',
            }
            _logger.info("::: creating inventory val {}".format(inventory_val))
            inventory_id = self.env['stock.inventory'].sudo().create(inventory_val)
            product_ids_ls = []
            inventory_line_obj = self.env['stock.inventory.line']
            lot_stock_id = bigcommerce_store_id.warehouse_id.lot_stock_id
            if response_data.status_code in [200, 201]:
                response_data = response_data.json()
                record = response_data.get('data')
                if bigcommerce_store_id.bigcommerce_product_skucode and record.get('sku'):
                    product_template_id = self.env['product.template'].sudo().search(
                        [('default_code', '=', record.get('sku')), (
                            'bigcommerce_store_id', '=', bigcommerce_store_id.id)], limit=1)
                else:
                    product_template_id = self.env['product.template'].sudo().search(
                        [('bigcommerce_product_id', '=', record.get('id')), (
                            'bigcommerce_store_id', '=', bigcommerce_store_id.id)], limit=1)
                if not product_template_id:
                    status, product_template_id = self.with_user(1).create_product_template(record,
                                                                                            bigcommerce_store_id)
                    if not status:
                        product_process_message = "%s : Product is not imported Yet! %s" % (
                            record.get('id'), product_template_id)
                        _logger.info("Getting an Error In Import Product Responase :{}".format(product_template_id))
                        raise UserError(product_process_message)
                    process_message = "Product Created : {}".format(product_template_id.name)
                    _logger.info("{0}".format(process_message))
                else:
                    product_name = record.get('name')
                    process_message = "{0} : Product Already Exist In Odoo!".format(product_template_id.name)
                    brand_id = self.env['bc.product.brand'].sudo().search(
                        [('bc_brand_id', '=', record.get('brand_id')), (
                                            'bigcommerce_store_id', '=', bigcommerce_store_id.id)], limit=1)
                    _logger.info("BRAND : {0}".format(brand_id))
                    product_template_id.write({
                        "list_price": record.get("price"),
                        "is_visible": record.get("is_visible"),
                        "bigcommerce_product_id": record.get('id'),
                        "bigcommerce_store_id": bigcommerce_store_id.id,
                        "default_code": record.get("sku"),
                        "is_imported_from_bigcommerce": True,
                        "is_exported_to_bigcommerce": True,
                        "name": product_name,
                        "x_studio_manufacturer": brand_id and brand_id.id,
                        "description_sale": record.get('description')
                    })
                    _logger.info("{0}".format(process_message))
                    self._cr.commit()
                self.env['product.attribute'].import_product_attribute_from_bigcommerce(warehouse_id,
                                                                                        bigcommerce_store_id,
                                                                                        product_template_id)
                self.env['bigcommerce.product.image'].sudo().import_multiple_product_image(bigcommerce_store_id,
                                                                                           product_template_id)
                if product_template_id.product_variant_count > 1:
                    api_operation_variant = "/v3/catalog/products/{}/variants".format(
                        product_template_id.bigcommerce_product_id)
                    variant_response_data = bigcommerce_store_id.with_user(1).send_get_request_from_odoo_to_bigcommerce(
                        api_operation_variant)
                    _logger.info(
                        "BigCommerce Get Product Variant Response : {0}".format(variant_response_data))
                    _logger.info(
                        "Response Status: {0}".format(variant_response_data.status_code))
                    if variant_response_data.status_code in [200, 201]:
                        api_operation_variant_response_data = variant_response_data.json()
                        variant_datas = api_operation_variant_response_data.get('data')
                        for variant_data in variant_datas:
                            option_labales = []
                            option_values = variant_data.get('option_values')
                            for option_value in option_values:
                                option_labales.append(option_value.get('label'))
                            v_id = variant_data.get('id')
                            product_sku = variant_data.get('sku')
                            _logger.info("Total Product Variant : {0} Option Label : {1}".format(
                                product_template_id.product_variant_ids, option_labales))
                            for product_variant_id in product_template_id.product_variant_ids:
                                if product_variant_id.mapped(
                                        lambda pv: pv.with_user(1).product_template_attribute_value_ids.mapped(
                                            'name') == option_labales)[0]:
                                    _logger.info(
                                        "Inside If Condition option Label =====> {0} Product Template "
                                        "Attribute Value ====> {1} variant_id====>{2}".format(
                                            option_labales, product_variant_id.with_user(1).mapped(
                                                'product_template_attribute_value_ids').mapped('name'),
                                            product_variant_id))
                                    if variant_data.get('price'):
                                        price = variant_data.get('price')
                                    else:
                                        price = variant_data.get('calculated_price')
                                    vals = {'default_code': product_sku, 'bc_sale_price': price,
                                            'bigcommerce_product_variant_id': v_id,
                                            'standard_price': variant_data.get('cost_price', 0.0)}
                                    variant_product_img_url = variant_data.get('image_url')
                                    if variant_product_img_url:
                                        image = base64.b64encode(
                                            requests.get(variant_product_img_url).content)
                                        vals.update({'image_1920': image})
                                    product_variant_id.with_user(1).write(vals)
                                    _logger.info("Product Variant Updated : {0}".format(
                                        product_variant_id.default_code))
                                    product_qty = variant_data.get('inventory_level')
                                    if product_qty > 0:
                                        inventory_line_val = {'product_id': product_variant_id.id,
                                                              'inventory_id': inventory_id and inventory_id.id,
                                                              'location_id': lot_stock_id.id,
                                                              'product_qty': record.get(
                                                                  'inventory_level'),
                                                              'product_uom_id': product_variant_id.uom_id.id,
                                                              }
                                        _logger.info("::: creating inventory line val {}".format(
                                            inventory_line_val))
                                        product_ids_ls.append(product_variant_id.id)
                                        inventory_line_obj.sudo().create(inventory_line_val)
                                    self._cr.commit()
                    else:
                        api_operation_variant_response_data = variant_response_data.json()
                        error_msg = api_operation_variant_response_data.get('errors')
                        _logger.info("ERROR >>>>>>> {}".format(error_msg))
                        # self.create_bigcommerce_operation_detail('product_attribute', 'import', '',
                        #                                          error_msg, operation_id, warehouse_id,
                        #                                          True, error_msg)
                else:
                    product_id = self.env['product.product'].sudo().search(
                        [('product_tmpl_id', '=', product_template_id.id)], limit=1)
                    inventory_line_val = {'product_id': product_id.id,
                                          'inventory_id': inventory_id and inventory_id.id,
                                          'location_id': lot_stock_id.id,
                                          'product_qty': record.get('inventory_level'),
                                          'product_uom_id': product_id.uom_id.id,
                                          }
                    _logger.info("::: creating inventory line val {}".format(inventory_line_val))
                    product_ids_ls.append(product_id.id)
                    inventory_line_obj.sudo().create(inventory_line_val)
                # quant_id = self.env['stock.quant'].with_user(1).search([('product_tmpl_id','=',product_template_id.id),('location_id','in',location)])
                # if len(quant_id) > 1:
                #     stock_quant_id = self.env['stock.quant'].with_user(1).search([('product_tmpl_id','=',product_template_id.id),('location_id','=',location_id.id)])
                #     _logger.info(" Stock Quant : {0}".format(stock_quant_id))
                #     stock_quant_id.with_user(1).unlink()
                # quant_id = self.env['stock.quant'].with_user(1).search([('product_tmpl_id','=',product_template_id.id),('location_id','in',location)])
                # if not quant_id:
                #     product_id = self.env['product.product'].sudo().search([('product_tmpl_id','=',product_template_id.id)],limit=1)
                #     vals = {'product_tmpl_id':product_template_id.id,'location_id':location_id.id,'inventory_quantity':record.get('inventory_level'),'product_id':product_id.id,'quantity':record.get('inventory_level')}
                #     self.env['stock.quant'].sudo().create(vals)
                # else:
                #     quant_id.sudo().write({'inventory_quantity':record.get('inventory_level'),'quantity':record.get('inventory_level')})
                inventory_id.write({'product_ids': [(6, 0, product_ids_ls)]})
                inventory_id.action_start()
                inventory_id.action_validate()
                _logger.info("Inventory Validated : {}".format(inventory_id.name))
                return {
                    'effect': {
                        'fadeout': 'slow',
                        'message': "Yeah! Successfully Product Imported".format(product_template_id.name),
                        'img_url': '/web/static/src/img/smile.svg',
                        'type': 'rainbow_man',
                    }
                }
        except Exception as e:
            _logger.info("Getting an Error In Import Product Responase".format(e))
            raise UserError("Getting an Error In Import Product Responase".format(e))

    # def request_export_update_product_data(self, product_id, bigcommerce_store_id, warehouse_id):
    #     images = []
    #     categ_ids = []
    #     data = {
    #         "type": "physical",
    #         "weight": product_id.weight or 1.0,
    #         "is_visible":product_id.is_visible
    #     }
    #     ecomm_categ = product_id.public_categ_ids.mapped('bigcommerce_product_category_id')
    #     for categ_id in ecomm_categ:
    #         categ_ids.append(int(categ_id))
    #     if not ecomm_categ:
    #         categ_ids.append(int(product_id.categ_id.bigcommerce_product_category_id))
    #     b2c_data = {
    #         # "id": product_id.b2c_bigcommerce_product_id,
    #         "name": product_id.name,
    #         'price': product_id.lst_price,
    #         # "categories": categ_ids
    #     }
    #     data.update(b2c_data)
    #     data.update({
    #         "inventory_tracking": 'product',
    #         "inventory_level": int(product_id.with_context(warehouse=warehouse_id.id).qty_available),
    #         "sku": product_id.default_code or ''
    #     })
    #     return data

    # def export_product_in_bigcommerce_from_product(self, bigcommerce_store_id, product_ids):
    #     try:
    #         operation_id = self.sudo().create_bigcommerce_operation('product', 'export', bigcommerce_store_id,
    #                                                                 'Processing...',
    #                                                                 bigcommerce_store_id.warehouse_id)
    #
    #         # product_ids = self.search([('bigcommerce_product_id', '!=', False)], order='id')
    #         for product in product_ids:
    #             images = []
    #             bc_product_id = product.bigcommerce_product_id
    #             if bc_product_id:
    #                 raise UserError("Product Already there in Bigcommerce : {}".format(product.name))
    #             api_operation = "/v3/catalog/products"
    #             # count += 1
    #             product_data = self.request_export_update_product_data(product, bigcommerce_store_id,bigcommerce_store_id.warehouse_id)
    #             web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #             if product.image_1920:
    #                 product_standard_image_url = web_base_url + '/web/image/product.product/{}/image_1024/'.format(product.product_variant_id.id)
    #                 product_tiny_image_url = web_base_url + '/web/image/product.product/{}/image_256/'.format(product.product_variant_id.id)
    #                 images.append({'image_url': product_standard_image_url, 'is_thumbnail': True,
    #                                'url_standard': product_standard_image_url, 'url_tiny': product_tiny_image_url,'description':'Main Image' + ":" + str(product.id)})
    #             for product_image_id in product.product_template_image_ids:
    #                 media_standard_image_url = web_base_url + '/web/image/product.image/{}/image_1024/'.format(
    #                     product_image_id.id)
    #                 media_tiny_image_url = web_base_url + '/web/image/product.image/{}/image_256/'.format(
    #                     product_image_id.id)
    #                 images.append({'image_url': media_standard_image_url, 'is_thumbnail': False,
    #                                'url_standard': media_standard_image_url, 'url_tiny': media_tiny_image_url,'description':product_image_id.name+ ":" + str(product_image_id.id)})
    #             # product_data.append(data)
    #             # bc_custom_field = self.export_bc_custom_fields(product,bigcommerce_store_id)
    #             # if bc_custom_field:
    #             #     product_data.update({'custom_fields':bc_custom_field})
    #             product_data.update({'images':images})
    #             response_data = bigcommerce_store_id.send_request_from_odoo_to_bigcommerce(product_data,
    #                                                                                        api_operation)
    #             print('product_data',product_data)
    #             print('response_data',response_data)
    #
    #             response = response_data.json()
    #             if response_data.status_code in [200, 201]:
    #                 bc_product_id = response.get('data') and response.get('data').get('id')
    #                 images = response.get('data') and response.get('data').get('images')
    #                 for image in images:
    #                     product_image_desc = image.get('description')
    #                     product_image_desc = product_image_desc.split(':')
    #                     if 'Main Image' in product_image_desc:
    #                         product.bc_product_image_id = image.get('id')
    #                     else:
    #                         ecom_product_image_id = self.env['product.image'].search([('id','=',product_image_desc[1])])
    #                         ecom_product_image_id.bc_product_image_id = image.get('id')
    #                 product.write({'bigcommerce_product_id': bc_product_id, 'is_exported_to_bigcommerce': True})
    #                 process_message = "Product Exported Sucessfully : {0} BC Product ID : {1}".format(product.name,
    #                                                                                                   bc_product_id)
    #                 self.sudo().create_bigcommerce_operation_detail('product', 'export', product_data, response,
    #                                                                 operation_id, bigcommerce_store_id.warehouse_id,
    #                                                                 False, process_message)
    #                 self._cr.commit()
    #             else:
    #                 error_message = response.get('errors')
    #                 self.sudo().create_bigcommerce_operation_detail('product', 'export', product_data, response,
    #                                                                 operation_id, bigcommerce_store_id.warehouse_id,
    #                                                                 True, error_message)
    #                 _logger.info("Getting an Error Product >>>>> {0} >>>>> Response: {1}".format(product.name,
    #                                                                                              response_data))
    #     except Exception as e:
    #         process_message = "Getting an Error In Export Product Responase:{0}".format(e)
    #         _logger.info("Getting an Error In Export Product Responase:{0}".format(e))
    #         self.sudo().create_bigcommerce_operation_detail('product', 'export', False, False, operation_id,
    #                                                         bigcommerce_store_id.warehouse_id, False,
    #                                                         process_message)
    #
    # def update_product_in_bigcommerce_from_product(self, bigcommerce_store_id, product_ids):
    #     try:
    #         # product_data = []
    #         # count = 1
    #         image_dict = {}
    #         operation_id = self.sudo().create_bigcommerce_operation('product', 'update', bigcommerce_store_id,
    #                                                                 'Processing...',
    #                                                                 bigcommerce_store_id.warehouse_id)
    #
    #         # product_ids = self.search([('bigcommerce_product_id', '!=', False)], order='id')
    #         web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #         for product in product_ids:
    #             images = []
    #             if product.image_1920:
    #                 product_standard_image_url = web_base_url + '/web/image/product.product/{}/image_1024/'.format(
    #                     product.product_variant_id.id)
    #                 product_tiny_image_url = web_base_url + '/web/image/product.product/{}/image_256/'.format(
    #                     product.product_variant_id.id)
    #                 image_dict = {'image_url': product_standard_image_url, 'is_thumbnail': True,
    #                               'url_standard': product_standard_image_url, 'url_tiny': product_tiny_image_url,
    #                               'description': 'Main Image' + ":" + str(product.id)}
    #             bc_product_id = product.bigcommerce_product_id
    #             bc_product_image_id = product.bc_product_image_id
    #             if bc_product_image_id:
    #                 image_dict.update({'id':int(bc_product_image_id)})
    #             if image_dict:
    #                 images.append(image_dict)
    #             for product_image_id in product.product_template_image_ids:
    #                 bc_product_image_id = product_image_id.bc_product_image_id
    #                 media_standard_image_url = web_base_url + '/web/image/product.image/{}/image_1024/'.format(
    #                     product_image_id.id)
    #                 media_tiny_image_url = web_base_url + '/web/image/product.image/{}/image_256/'.format(
    #                     product_image_id.id)
    #                 image_dict = {'image_url': media_standard_image_url, 'is_thumbnail': False,
    #                                'url_standard': media_standard_image_url, 'url_tiny': media_tiny_image_url,
    #                                'description': product_image_id.name + ":" + str(product_image_id.id)}
    #                 if bc_product_image_id:
    #                     image_dict.update({'id':int(bc_product_image_id)})
    #                     images.append(image_dict)
    #                 if not bc_product_image_id and not product_image_id.bc_product_image_id:
    #                     images.append(image_dict)
    #             if not bc_product_id:
    #                 raise UserError("Product Not Sync : {}".format(product.name))
    #             api_operation = "/v3/catalog/products/{}".format(bc_product_id)
    #             # count += 1
    #             product_data = self.request_export_update_product_data(product, bigcommerce_store_id,
    #                                                                    bigcommerce_store_id.warehouse_id)
    #             product_data.update({'images':images})
    #             _logger.info("Product Data : {}".format(product_data))
    #             print('product_data', product_data)
    #             print('api_operation', api_operation)
    #             response_data = bigcommerce_store_id.update_request_from_odoo_to_bigcommerce(product_data,
    #                                                                                          api_operation)
    #             print('response_data', response_data)
    #             if response_data.status_code in [200, 201]:
    #                 # _logger.info("Get Successfull Response {0}".format(count))
    #                 response = response_data.json()
    #                 print('response', response)
    #
    #                 process_message = "Product Update Sucessfully : {0}".format(product.name)
    #                 self.sudo().create_bigcommerce_operation_detail('product', 'update', product_data, response,
    #                                                                 operation_id, bigcommerce_store_id.warehouse_id,
    #                                                                 False, process_message)
    #                 operation_id.bigcommerce_message = process_message
    #                 self._cr.commit()
    #             else:
    #                 _logger.info("Getting an Error Product >>>>> {0} >>>>> Response: {1}".format(product.name,
    #                                                                                              response_data.json()))
    #                 process_message = "Product Not Updated Sucessfully : {0}".format(product.name)
    #                 self.sudo().create_bigcommerce_operation_detail('product', 'update', product_data, response_data.json(),
    #                                                                 operation_id, bigcommerce_store_id.warehouse_id,
    #                                                                 True, process_message)
    #             # if count == 6:
    #             #     count = 1
    #             #     time.sleep(10)
    #     except Exception as e:
    #         process_message = "Getting an Error In Import Product Responase:{0}".format(e)
    #         _logger.info("Getting an Error In Import Product Responase:{0}".format(e))
    #         self.sudo().create_bigcommerce_operation_detail('product', 'update', False, False, operation_id,
    #                                                         bigcommerce_store_id.warehouse_id, False,
    #                                                         process_message)

    def request_update_product_inventory_data(self, product_id, warehouse_id):
        # print('warehouse_id', warehouse_id)
        # print('int(product_id.with_context(warehouse=warehouse_id.id).qty_available)',
        #       int(product_id.with_context(warehouse=warehouse_id.id).qty_available))
        data = {
            "inventory_tracking": 'product',
            "inventory_level": int(product_id.with_context(warehouse=warehouse_id.id).qty_available),
        }
        return data

    # def update_product_inventory_cron(self,product_ids=False,bigcommerce_store_ids=False):
    #     if not bigcommerce_store_ids:
    #         bigcommerce_store_ids = self.env['bigcommerce.store.configuration'].search([])
    #     for bigcommerce_store_id in bigcommerce_store_ids:
    #         try:
    #             product_data = []
    #             count = 1
    #             from_datetime = datetime.now() - relativedelta(minutes=5)
    #             if not product_ids:
    #                 move_ids = self.env['stock.move'].search(
    #                     [('company_id', '=', bigcommerce_store_id.warehouse_id.company_id.id),
    #                      ('state', 'in', ['done', 'cancel']),
    #                      ('write_date', '>=', str(datetime.strftime(from_datetime, '%Y-%m-%d %H:%M:%S')))])
    #                 product_ids = move_ids.mapped('product_id').filtered(lambda pp:pp.bigcommerce_product_id != False)
    #             operation_id = self.sudo().create_bigcommerce_operation('product', 'update', bigcommerce_store_id,
    #                                                                     'Processing...',
    #                                                                     bigcommerce_store_id.warehouse_id)
    #             # if not product_ids:
    #             #     product_ids = self.search([('bigcommerce_product_id', '!=', False)], order='id')
    #             for product in product_ids:
    #                 api_operation = "/v3/catalog/products/{}".format(product.bigcommerce_product_id)
    #                 count += 1
    #                 product_data = self.request_update_product_inventory_data(product, bigcommerce_store_id.warehouse_id)
    #                 print('product_data',product_data)
    #                 print('api_operation',api_operation)
    #                 response_data = bigcommerce_store_id.update_request_from_odoo_to_bigcommerce(product_data,
    #                                                                                              api_operation)
    #                 print('response_data',response_data)
    #
    #                 if response_data.status_code in [200, 201]:
    #                     response = response_data.json()
    #                     _logger.info("Get Successfull Response {0} : {1}".format(count,response))
    #                     process_message = "Product Update Sucessfully : {0}".format(product.name)
    #                     self.sudo().create_bigcommerce_operation_detail('product', 'update', data, response,
    #                                                                     operation_id, bigcommerce_store_id.warehouse_id,
    #                                                                     False, process_message)
    #                     self._cr.commit()
    #                 else:
    #                     _logger.info("Getting an Error Product >>>>> {0} >>>>> Response: {1}".format(product.name,
    #                                                                                                  response_data))
    #                 if count == 10:
    #                     count = 1
    #                     time.sleep(6)
    #         except Exception as e:
    #             process_message = "Getting an Error In Update Product Inventory Responase:{0}".format(e)
    #             _logger.info("Getting an Error In Update Product Inventory Responase:{0}".format(e))
    #             self.sudo().create_bigcommerce_operation_detail('product', 'update', False, False, operation_id,
    #                                                             bigcommerce_store_id.warehouse_id, False,
    #                                                             process_message)
