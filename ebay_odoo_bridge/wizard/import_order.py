# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2019-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from collections import Iterable
from odoo.exceptions import UserError

from odoo import api, fields, models
from odoo.tools import date_utils
from odoo.addons.odoo_multi_channel_sale.tools import _unescape

import logging
_logger = logging.getLogger(__name__)


class ImportEbayOrders(models.TransientModel):
	_name = "import.ebay.orders"

	_description = "Import Ebay Orders"
	_output_selector = "HasMoreOrders,PageNumber,PaginationResult,PaginationResult.TotalNumberOfEntries,OrderArray,OrderArray.Order"

	@api.model
	def _create_country(self, CountryName, CountryCode):
		country_obj = self.env['res.country']
		exists = country_obj.search([('name', '=', CountryName)])
		if exists:
			country_id = exists[0].id
		else:
			country_id = country_obj.create(
				{'name': CountryName, 'code': CountryCode}).id
		return country_id

	def get_default_payment_method(self, journal_id):
		""" @params journal_id: Journal Id for making payment
										@params context : Must have key 'ecommerce' and then return payment  method based on Odoo Bridge used else return the default payment method for Journal
										@return: Payment method ID(integer)"""

		payment_method_ids = self.env['account.journal'].browse(
			journal_id)._default_inbound_payment_methods()
		if payment_method_ids:
			return payment_method_ids[0].id
		return False

	def _getTaxName(self, ebay_item, ebay_order):
		tax_type = ebay_item.get('Taxes',{}).get('TaxDetails',{}).get('Imposition')
		tax_pecent = ebay_order.get('ShippingDetails',{}).get(tax_type,{}).get('SalesTaxPercent','0.0')
		tax_vals = {
				'rate': tax_pecent,
				'name': 'Tax %s'%(tax_pecent),
				'tax_type'    : 'percent',
				'include_in_price': False,
		}
		return tax_vals

	@api.model
	def CreateShippingInvoiceAddress(self, ebay_order):
		""" Creates shipping address and invoice address and returns dictionary of these address values"""
		vals = {}
		EbayCustomerInfo = ebay_order[
			'TransactionArray']['Transaction'][0]['Buyer']
		ebay_cust_shipping_adrs = ebay_order['ShippingAddress']
		vals['invoice_partner_id'] = ebay_order['BuyerUserID']
		name = ''
		if EbayCustomerInfo.get('UserFirstName'):
			name = EbayCustomerInfo.get('UserFirstName')+EbayCustomerInfo.get('UserLastName', '')
		if name == '':
			if ebay_cust_shipping_adrs.get('Name'):
				name = ebay_cust_shipping_adrs.get('Name')
			else:
				name = 'No Name'
		vals['customer_name'] = name
		vals['invoice_name'] = name
		if EbayCustomerInfo.get('Email') and EbayCustomerInfo.get('Email') != 'Invalid Request':
			vals['customer_email'] = EbayCustomerInfo.get('Email')
			vals['invoice_email'] = EbayCustomerInfo.get('Email')
		else:
			vals['customer_email'] = 'No Email'
			vals['invoice_email'] = 'No Email'
		vals['invoice_street'] = ebay_cust_shipping_adrs.get('Street1')
		vals['invoice_street2'] = ebay_cust_shipping_adrs.get('Street2')
		if ebay_cust_shipping_adrs.get('Phone') and ebay_cust_shipping_adrs.get('Phone') != 'Invalid Request':
			vals['invoice_phone'] = ebay_cust_shipping_adrs.get('Phone')
		vals['invoice_city'] = ebay_cust_shipping_adrs.get('CityName')
		vals['invoice_zip'] = ebay_cust_shipping_adrs.get('PostalCode')
		vals['invoice_state_id'] = ebay_cust_shipping_adrs.get(
			'StateOrProvince')
		vals['invoice_country_id'] = ebay_cust_shipping_adrs.get('Country')
		return vals

	@api.model
	def _CreateAttributeString(self, EbayAttibuteString):
		if EbayAttibuteString['VariationSpecifics']['NameValueList']:
			EbayNameValueList = EbayAttibuteString[
				'VariationSpecifics']['NameValueList']
			AttString = []
			if isinstance(EbayNameValueList, (dict)):
				EbayNameValueList = [EbayNameValueList]
			for EbayValue in EbayNameValueList:
				AttString.append(_unescape(EbayValue['Value']))
			AttString.sort()
			AttString = ",".join(str(x) for x in AttString)
			return AttString

	@api.model
	def _GetFeedOrderProduct(self, ebay_item, channel_id):
		res = {}
		if isinstance(ebay_item, (list)):
			ebay_item = ebay_item[0]
		res["ProductFeedId"] = self.env['import.ebay.products'].with_context(OrderCall=True).get_product_using_product_id(
			ebay_item['Item']['ItemID'], channel_id)
		return res

	@api.model
	def GetVariantID(self, ebay_item):
		variant_id = 'No Variants'
		if ebay_item.get('Variation'):
			variant_id = self._CreateAttributeString(ebay_item['Variation'])
		return variant_id

	@api.model
	def GetFeedOrderProductValues(self, ebay_item=False, ChannelID=False):
		api = self._context.get('api')
		feed_vals = {}
		feed_vals.update({
			'line_price_unit': ebay_item['TransactionPrice']['value'],
			'line_product_uom_qty': ebay_item['QuantityPurchased'],
			'line_product_id': ebay_item['Item']['ItemID'],
			'line_variant_ids': self.GetVariantID(ebay_item),
			'line_name':     ebay_item['Item']['Title'],
			'line_taxes':   []
		})
		self._GetFeedOrderProduct(ebay_item, ChannelID)
		callData = {
					'IncludeTaxTable':True,
					'IncludeItemSpecifics': True,
					'ItemID': ebay_item['Item']['ItemID']
				}
		response = api.execute('GetItem', callData)
		result = response.dict()
		if result['Ack']=='Success':
			if 'VATDetails' in result['Item']:
				tax_pecent = result['Item']['VATDetails'].get('VATPercent','0.0')
				tax_vals = {
					'rate': tax_pecent,
					'name': 'Tax %s'%(tax_pecent),
					'tax_type'    : 'percent',
					'include_in_price': False,
				}
				feed_vals["line_taxes"] = [tax_vals]
		return {'feed_vals': feed_vals}

	@api.model
	def CreateFeedOrderLines(self, ebay_order=False, ChannelID=False):
		context = dict(self._context or {})
		feed_vals = {}
		ProductFeedCreated = False
		ebay_items = ebay_order['TransactionArray']['Transaction']
		shipping = ebay_order.get('ShippingServiceSelected')
		# shipping_cost =
		if len(ebay_items) <= 1 and not shipping:
			if isinstance(ebay_items, (list)):
				ebay_item = ebay_items[0]
			res = self.with_context(**context).GetFeedOrderProductValues(ebay_item, ChannelID)
			feed_vals.update(res.get('feed_vals'))
			if not feed_vals["line_taxes"]:
				tax_vals = self._getTaxName(ebay_item, ebay_order)
				if tax_vals:
					feed_vals["line_taxes"] = [tax_vals]
		else:
			feed_vals.update({'line_type': 'multi'})
			line_vals_list = [(5,0)]
			for ebay_item in ebay_items:
				line_vals = {}
				res = self.with_context(**context).GetFeedOrderProductValues(ebay_item, ChannelID)
				line_vals.update(res.get('feed_vals'))
				if not line_vals["line_taxes"]:
					tax_vals = self._getTaxName(ebay_item, ebay_order)
					if tax_vals:
						line_vals["line_taxes"] = [tax_vals]
				line_vals_list.append((0, 0, line_vals))
			if ebay_order.get('ShippingServiceSelected'):
				shipping_info = ebay_order.get('ShippingServiceSelected')
				line_vals_list.append((0, 0, {
					'line_name'           : shipping_info.get('ShippingService'),
					'line_product_uom_qty': 1,
					'line_source'         : 'delivery',
					'line_product_id'     : shipping_info.get('ShippingService'),
					'line_price_unit'     : shipping_info.get('ShippingServiceCost').get('value')
				}))
			feed_vals.update({'line_ids': line_vals_list})

		if res.get('product_res', {}).get('ProductFeedId'):
			ProductFeedCreated = True
		return {'feed_vals': feed_vals, 'ProductFeedCreated': ProductFeedCreated}

	@api.model
	def _CreateOrderFeedVal(self, ebay_order, partner_store_id):
		context = self._context.copy() or {}
		ChannelID = context.get('channel_id')
		OrderFeedVals = {
			'partner_id': partner_store_id,
			'channel_id': ChannelID.id,
			'payment_method': ebay_order['CheckoutStatus']['PaymentMethod'],
			'name': ebay_order['OrderID'],
			'store_id': ebay_order['OrderID'],
			'order_state': ebay_order['OrderStatus'],
			'line_source': 'product',
			'currency': ebay_order.get('TransactionArray').get('Transaction')[0].get('TransactionPrice').get('_currencyID'),
			'date_order': ebay_order.get('CreatedTime', False).replace('T',' ').split('.')[0],
			'date_invoice': ebay_order.get('PaidTime', False).replace('T',' ').split('.')[0],
			'confirmation_date': ebay_order.get('CreatedTime', False).replace('T',' ').split('.')[0],
		}
		shipping_vals = self.CreateShippingInvoiceAddress(ebay_order)
		OrderFeedVals.update(shipping_vals)
		if ebay_order.get('ShippingServiceSelected'):
			shipping_service = ebay_order.get('ShippingServiceSelected')
			OrderFeedVals['carrier_id'] = shipping_service.get(
				'ShippingService')
		res = self.with_context(**context).CreateFeedOrderLines(ebay_order, ChannelID)
		OrderFeedVals.update(res.get('feed_vals'))
		return OrderFeedVals

	@api.model
	def _CreateOdooFeedValsList(self, EbayOrders):
		context = dict(self._context or {})
		FeedList = []
		ChannelID = context['channel_id']
		for EbayOrder in EbayOrders:
			if EbayOrder.get('TransactionArray').get('Transaction'):
				store_id = EbayOrder.get('TransactionArray').get(
					'Transaction')[0].get('Item').get('ItemID')
				if ChannelID.debug == 'enable':
					_logger.info('--------Ebay Created  Order Date-----------%r', EbayOrder.get('TransactionArray').get(
						'Transaction')[0].get('CreatedDate'))
			feed_val = self.with_context(context)._CreateOrderFeedVal(
				EbayOrder, EbayOrder["BuyerUserID"])
			FeedList.append(feed_val)
		return FeedList

	@api.model
	def _FetchEbayOrders(self, api):
		message = ""
		context = dict(self._context or {})
		channel_id = context.get('channel_id')

		page = context['page']
		result = []
		EntriesPerPage = context['per_page']
		try:
			while page:
				callData = {
					'DetailLevel': 'ReturnAll',  # ItemReturnDescription
					'Pagination': {'EntriesPerPage': EntriesPerPage, 'PageNumber': page},
					'CreateTimeFrom': context['from_datetime'],
					'CreateTimeTo':  context['to_datetime'],
					# 'OutputSelector': self._output_selector,
					'SortingOrder': 'Ascending',
				}
				if context.get('order_id'):
					callData.update({
						'OrderIDArray': {'OrderID': str(context.get('order_id'))},
						'OrderRole': 'Seller'
					})
				if context.get('order_status'):
					callData['OrderStatus'] = context['order_status']
				api.config.set("compatibility", '1113') #For new Order Number
				response = api.execute('GetOrders', callData)
				result_dict = response.dict()
				if channel_id.debug == 'enable':
					_logger.info('-------Response---------- %r', result_dict)
				if result_dict.get('Ack') == 'Success':
					if not result_dict['OrderArray']:
						message = 'No Orders To Import In This Time Interval..'
						_logger.info(message)
						break
					elif result_dict['OrderArray'] and result_dict['OrderArray']['Order'] and type(result_dict['OrderArray']['Order']) == list:
						result.extend(result_dict['OrderArray']['Order'])
					else:
						result.append(result_dict['OrderArray']['Order'])
					yield result, result_dict['HasMoreOrders'] == 'true'
				else:
					message = message + 'STATUS : %s <br>' % result_dict['Ack']
					message = message + \
						'PAGE : %s <br>' % result_dict['PageNumber']
					message = message + \
						'ErrorCode : %s <br>' % result_dict[
							'Errors']['ErrorCode']
					message = message + \
						'ErrorParameters : %s <br>' % result_dict[
							'Errors']['ErrorParameters']
					message = message + \
						"LongMessage: %s <br>" % result_dict[
							'Errors']['LongMessage']
					_logger.info(message)
					break
		except Exception as e:
			_logger.info(
				'--------Exception in _FetchEbayOrders-------------%r', e)

	@api.model
	def import_now(self, **kw):
		li_feed_vals = [] #Stores list of order feeds vals
		context = dict(self._context or {})
		ConfObj = self.env["multi.channel.sale"]
		ChannelID = kw.get('channel_id')
		api_obj = ConfObj._get_api(ChannelID, 'Trading')

		if api_obj['status']:
			default_data = ConfObj._get_default_data(ChannelID)
			if kw.get('filter_type') in ['date_range', 'id']:
				context['order_status'] = kw.get('order_status')
				context['ebay_sellerid'] = default_data[
					'data']['ebay_sellerid']
				context['from_datetime'] = kw.get('updated_at_min')
				context['to_datetime'] = kw.get('updated_at_max')
				context['order_id'] = kw.get('object_id', '')
				context['channel_id'] = ChannelID
				context['per_page'] = kw.get('page_size', 1)
				context['page'] = kw.setdefault('page', 1)
				context['api'] = api_obj['api']

				result = self.with_context(
					context)._FetchEbayOrders(api_obj['api'])
				if isinstance(result, Iterable):
					for orders, has_more in result:
						li_feed_vals = self.with_context(
							context)._CreateOdooFeedValsList(orders)
						if has_more:kw['page'] += 1
						else:
							kw['page'] = 0
							if kw.get('cron_service'):
								if len(li_feed_vals) < kw.get('page_size'):
									ChannelID.set_channel_date(record='order')
						return li_feed_vals, kw

					if kw.get('cron_service'):
						ChannelID.set_channel_date(record='order')
			else:
				raise UserError("Filter 'all' is not available for importing sale order")
		return li_feed_vals, kw

	# ebay_sorting_order = fields.Selection(
	#     [('Ascending', 'Ascending'), ('Descending', 'Descending')],
	#     string='Sort By',
	#     default="Ascending",
	#     help="sorting order of the returned orders")
