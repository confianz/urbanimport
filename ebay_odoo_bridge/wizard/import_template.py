# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2019-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
import base64  # file encode
import urllib.request  # file download from url
from collections import Iterable
import re
from odoo.exceptions import UserError, ValidationError

from odoo import api, fields, models
from odoo.tools import date_utils
from odoo.addons.odoo_multi_channel_sale.tools import _unescape
import datetime
import logging
_logger = logging.getLogger(__name__)


class ImportEbayProducts(models.TransientModel):
	_name = "import.ebay.products"
	_description = "Import Ebay Templates"
	_output_selector = "HasMoreItems,Ack,PageNumber,Errors,PaginationResult,ItemArray.Item.Title,ItemArray.Item.ItemID,ItemArray.Item.Description,ItemArray.Item.PrimaryCategory,ItemArray.Item.SellingStatus.CurrentPrice.value,ItemArray.Item.Quantity,ItemArray.Item.Variations"

	@api.model
	def _CalculateSalesTax(self, ebay_tax):
		TaxOBj = self.env['account.tax']
		MapObj = self.env['channel.account.mappings']
		amount = float(ebay_tax['SalesTaxPercent'])
		name = 'Tax ' + str(amount) + '%'
		exists = MapObj.search([('name', '=', name)])
		tax_id = 0
		if exists:
			tax_id = exists[0].OdooTaxID
		else:
			if amount != 0.0:
				tax_data = {
					'name': name,
					'amount_type': 'percent',
					'amount': float(ebay_tax['SalesTaxPercent']),
					'type_tax_use': 'sale',
					'description': ebay_tax['SalesTaxPercent'] + '%'
				}
				tax_id = TaxOBj.create(tax_data).id
				if tax_id:
					MapObj.create({'StoreTaxValue': ebay_tax[
						'SalesTaxPercent'], 'OdooTaxID': tax_id, 'TaxName': tax_id, 'name': name})
		return tax_id

	@api.model
	def CreateOdooVariantFeed(self, EbayProdData):
		context = dict(self._context or {})
		variant_list = []
		if EbayProdData['Variations'].get('Variation'):
			variants = EbayProdData['Variations']['Variation']
			if isinstance(variants, (dict)):
				variants = [variants]
			for variant_line in variants:
				name_vale_list = variant_line[
					'VariationSpecifics']['NameValueList']
				attr_string = self._CreateAttributeString(variant_line)
				if attr_string:
					varinat_store_id = attr_string
				else:
					varinat_store_id = 'No Variants'
				if isinstance(name_vale_list, (dict)):
					name_vale_list = [name_vale_list]
				name_value = []
				qty_available = int(variant_line.get('Quantity')) - \
					int(variant_line.get('SellingStatus').get('QuantitySold'))
				for nm in name_vale_list:
					name_value.append(
						{'name': nm['Name'], 'value': nm['Value']})
				vals = {
					'name_value': name_value,
					'list_price': variant_line.get('StartPrice').get('value'),
					'qty_available': qty_available, 'store_id': varinat_store_id,
					'default_code': variant_line.get('SKU')
				}
				if "UPC" in variant_line.get("VariationProductListingDetails", {}):
					vals["wk_product_id_type"] = "wk_upc"
					key = "UPC"
				if "EAN" in variant_line.get("VariationProductListingDetails", {}) and not vals.get("wk_product_id_type"):
					vals["wk_product_id_type"] = "wk_ean"
					key = "EAN"
				if "ISBN" in variant_line.get("VariationProductListingDetails", {}) and not vals.get("wk_product_id_type"):
					vals["wk_product_id_type"] = "wk_isbn"
					key = "ISBN"
				if vals.get("wk_product_id_type"):
					barcode = variant_line.get(
						"VariationProductListCreateOdooVariantFeedingDetails", {}).get(key, False) != context.get('channel_id').ebay_barcode_unavailable_text \
							and variant_line.get("VariationProductListingDetails", {}).get(key, False)

					vals["barcode"] = barcode
				variant_list.append(vals)

		return variant_list

	@api.model
	def GetEbayProductDescription(self, description):
		if description:
			desc = re.sub('<[^<]+?>', '', description)
			desc = re.sub(r'&(.*?);', '', desc)
			description = desc
		else:
			description = 'No Description'
		return description

	@api.model
	def GetOdooTemplateData(self, EbayProdData, ChannelID):
		qty_available = int(EbayProdData.get('Quantity')) - \
			int(EbayProdData.get('SellingStatus').get('QuantitySold'))
		template_data = {
			'name': _unescape(EbayProdData.get('Title')),
			'list_price': EbayProdData.get('SellingStatus').get('CurrentPrice').get('value', ''),
			'store_id': EbayProdData.get('ItemID'),
			'channel_id': ChannelID.id,
			'channel': 'ebay',
			'qty_available': qty_available,
			'default_code': EbayProdData.get('SKU', ''),
			'variants': [],
		}
		if ChannelID.ebay_use_html_description:
			template_data['ebay_description_html'] = EbayProdData['Description']
		else:
			template_data['description_sale'] = self.GetEbayProductDescription(
				EbayProdData['Description'])
		if "UPC" in EbayProdData.get("ProductListingDetails", {}):
			template_data["wk_product_id_type"] = "wk_upc"
			key = "UPC"
		if "EAN" in EbayProdData.get("ProductListingDetails", {}) and not template_data.get("wk_product_id_type"):
			template_data["wk_product_id_type"] = "wk_ean"
			key = "EAN"
		if "ISBN" in EbayProdData.get("ProductListingDetails", {}) and not template_data.get("wk_product_id_type"):
			template_data["wk_product_id_type"] = "wk_isbn"
			key = "ISBN"

		if template_data.get("wk_product_id_type"):
			barcode = EbayProdData.get(
				"ProductListingDetails", {}).get(key, False) != ChannelID.ebay_barcode_unavailable_text and EbayProdData.get(
				"ProductListingDetails", {}).get(key, False)
			template_data["barcode"] = barcode

		if "BrandMPN" in EbayProdData.get("ProductListingDetails", {}):
			template_data["ebay_MPN"] = EbayProdData.get("ProductListingDetails", {}).get("BrandMPN").get("Brand", False)
			template_data["ebay_Brand"] = EbayProdData.get("ProductListingDetails", {}).get("BrandMPN").get("MPN", False)
		return template_data

	@api.model
	def _CreateOdooFeed(self, EbayProdData):
		context = dict(self._context or {})
		if isinstance(EbayProdData, (list)):
			EbayProdData = EbayProdData[0]
		FeedObj = self.env['product.feed']
		status = False
		FeedsUpdated = False
		StausMsg = ''
		feed_id = False
		try:
			if context.get('channel_id'):
				ChannelID = context['channel_id']

			context['ebay_item_id'] = EbayProdData['ItemID']
			template_data = self.GetOdooTemplateData(EbayProdData, ChannelID)
			if EbayProdData.get('PictureDetails') and EbayProdData['PictureDetails'].get('PictureURL'):
				image_url = EbayProdData['PictureDetails']['PictureURL']
				if isinstance(image_url, (list)):
					image_url = image_url[0]
				photo = base64.encodestring(
					urllib.request.urlopen(image_url).read())
				template_data.update({'image': photo})
			if EbayProdData.get('Variations'):
				variant_list = self.CreateOdooVariantFeed(
					EbayProdData)
				if variant_list:
					template_data.update({'feed_variants': variant_list})
			# if EbayProdData.has_key('ShippingDetails') and EbayProdData['ShippingDetails'].has_key('SalesTax'):
			#   tax_id = self._alulateSalesTax(EbayProdData['ShippingDetails']['SalesTax'])
			#   if tax_id:
			#       template_data.update({'taxes_id':[(6, 0, [tax_id])]})
			feed_id = FeedObj.create(template_data)
			if ChannelID.debug == 'enable':
				_logger.info(
					'------------Template %s created-----', feed_id.name)
			status = True
		except Exception as e:
			_logger.info('------------Exception-CreateOdooTemplate------%r', e)
			StausMsg = "Error in Fetching Product: %s" % e
		finally:
			return {
				'status': status,
				'StausMsg': StausMsg,
				'product_feed_id': feed_id,
			}

	@api.model
	def _CreateAttributeString(self, EbayAttibuteString):
		if EbayAttibuteString['VariationSpecifics']['NameValueList']:
			EbayNameValueList = EbayAttibuteString[
				'VariationSpecifics']['NameValueList']
			AttString = []
			if isinstance(EbayNameValueList, (dict)):
				EbayNameValueList = [EbayNameValueList]
			for EbayValue in EbayNameValueList:
				AttString.append(EbayValue['Value'])
			AttString.sort()
			AttString = ",".join(str(x) for x in AttString)
			return AttString

	@api.model
	def get_product_data_using_product_id(self, item_id, ChannelID):
		api_obj = self.env["multi.channel.sale"]._get_api(ChannelID, 'Trading')
		context = dict(self._context or {})
		context.update({'channel_id': ChannelID})
		res = {}
		StausMsg = ''
		if api_obj['status']:
			try:
				result = []
				callData = {
					'DetailLevel': 'ReturnAll',  # ItemReturnDescription
					'ItemID': item_id,
					'IncludeItemSpecifics': True,
					'IncludeTaxTable': True
				}
				response = api_obj['api'].execute('GetItem', callData)
				result_dict = response.dict()
				if result_dict['Ack'] == 'Success':
					if type(result_dict['Item']) == list:
						result.extend(result_dict['ItemArray']['Item'])
					else:
						result.append(result_dict['Item'])
			except Exception as e:
				StausMsg += 'Error in geting the product from Ebay %s' % str(e)
				_logger.info(
					'----------Exception in get_product_data_using_product_id--------%r', e)
			finally:
				return {'result': result, 'StausMsg': StausMsg}

	@api.model
	def get_product_using_product_id(self, item_id, ChannelID):
		context = dict(self._context or {})
		context.update({'channel_id': ChannelID})
		resp = self.get_product_data_using_product_id(item_id, ChannelID)
		feed = False
		result = self.with_context(context)._CreateFeedVals(resp.get('result'))
		if not context.get('OrderCall'):
			return result
		if result:
			vals = result[0]
			vals['feed_variants'] = [(0,0, vals.pop('variants')[0])] if vals.get('variants') else vals.pop('variants')
			feed = self.env["product.feed"].create(vals)
		return feed

	@api.model
	def _CreateOdooFeeds(self, ebay_products):
		context = dict(self._context or {})
		create_ids = []
		final_message = ""
		res = {}
		if context.get('channel_id'):
			ChannelID = context['channel_id']

		for ebay_product in ebay_products:
			res = self.with_context(context)._CreateOdooFeed(ebay_product)
			final_message += res['StausMsg']
			if res["status"]:
				create_ids.append(res.get('product_feed_id'))

		return {'message': final_message,
				'create_ids': create_ids,
				}

	def _CreateFeedVals(self, ebay_products):
		product_li = []
		context = self._context.copy() or {}
		for EbayProdData in ebay_products:
			extra_categ = []
			if context.get('channel_id'):
				ChannelID = context['channel_id']

			context['ebay_item_id'] = EbayProdData['ItemID']
			template_data = self.GetOdooTemplateData(EbayProdData, ChannelID)
			if EbayProdData.get('PictureDetails') and EbayProdData['PictureDetails'].get('GalleryURL'):
				image_url = EbayProdData['PictureDetails']['GalleryURL']
				template_data["image_url"] = image_url

				# image_url = EbayProdData['PictureDetails']['PictureURL']
				# if isinstance(image_url, (list)):
				# 	image_url = image_url[0]
				# photo = base64.encodestring(urllib.request.urlopen(image_url).read())
				# template_data.update({'image': photo})
			if EbayProdData.get('Variations'):
				variant_list = self.CreateOdooVariantFeed(EbayProdData)
				if variant_list:
					template_data.update({'variants': variant_list})
			if EbayProdData.get("PrimaryCategory"):
				extra_categ += [EbayProdData.get(
					"PrimaryCategory").get('CategoryID')]
			if EbayProdData.get("SecondaryCategory"):
				extra_categ += [EbayProdData.get(
					"SecondaryCategory").get('CategoryID')]
			if extra_categ:
				template_data["extra_categ_ids"] = ",".join(extra_categ)
			product_li.append(template_data)
		return product_li

	@api.model
	def _FetchStoreSellerItems(self, api):
		message = 'No Products To Import In This Time Interval..'
		context = dict(self._context or {})

		from_datetime = context['from_datetime']
		to_datetime = context['to_datetime']
		EntriesPerPage = context['per_page']
		page = context['page']

		try:
			while page:
				interval = datetime.timedelta(days=120)

				sdate = from_datetime
				edate = to_datetime
				period_start = sdate
				result = []
				while period_start < edate:
					period_end = min(period_start + interval, edate)
					# print('inside----------------------', period_start,period_end)
					# x = input('Enter your name:')

					callData = {
						'DetailLevel': 'ReturnAll',  # ItemReturnDescription
						'Pagination': {'EntriesPerPage': EntriesPerPage, 'PageNumber': page},
						'UserID': context['ebay_sellerid'],
						'IncludeVariations': True,
						'StartTimeFrom': period_start,
						'StartTimeTo': period_end,
						# 'OutputSelector':self._output_selector,
					}
					if context.get('StoreCategID'):
						callData['CategoryID'] = context['StoreCategID']
					response = api.execute('GetSellerList', callData)

					result_dict = response.dict()
					# _logger.info('-----------result_dict-----%r',result_dict)
					if result_dict['Ack'] == 'Success':
						if result_dict['ItemArray']:
							if type(result_dict['ItemArray']['Item']) == list:
								result.extend(result_dict['ItemArray']['Item'])
							else:
								result.append(result_dict['ItemArray']['Item'])

							# yield result, result_dict['HasMoreItems'] == 'true'
						else:
							_logger.info(message)
							# break
							# continue
					else:
						message = message + 'STATUS : %s <br>' % result_dict['Ack']
						message = message + \
							'PAGE : %s <br>' % result_dict['PageNumber']
						message = message + \
							'ErrorCode : %s <br>' % result_dict[
								'Errors']['ErrorCode']
						message = message + \
							'ShortMessage : %s <br>' % result_dict[
								'Errors']['ShortMessage']
						message = message + \
							"LongMessage: %s <br>" % result_dict[
								'Errors']['LongMessage']
						_logger.info(message)
						# break
						# continue
					period_start = period_end
				yield result, True
		except Exception as e:
			_logger.info(
				'------------Exception--FetchStoreSellerItems-----%r', e)

	def import_now(self, **kw):
		li_feed_vals = [] #Stores list of product feeds vals
		context = dict(self._context or {})
		ChannelId = kw.get("channel_id")
		context["channel_id"] = ChannelId
		MultiChannel = self.env["multi.channel.sale"]

		APIResult = MultiChannel._get_api(ChannelId, 'Trading')
		if APIResult['status']:
			if kw.get('filter_type') == 'date_range':
				default_data = MultiChannel._get_default_data(ChannelId)
				interval = datetime.timedelta(days=120)

				sdate = kw.get(
						'updated_at_min')
				edate = kw.get(
						'updated_at_max')
				period_start = sdate
				# while period_start < edate:
				# period_end = min(period_start + interval, edate)
				if kw.get('category_id'):
					context['StoreCategID'] = kw.get('category_id')
				context['from_datetime'] = period_start
				context['to_datetime'] = edate
				context['ebay_sellerid'] = default_data[
					'data']['ebay_sellerid']
				context['per_page'] = kw.get('page_size', 1)
				context['page'] = kw.setdefault('page', 1)


				result = self.with_context(
					context)._FetchStoreSellerItems(APIResult['api'])
				# print('resultresultresultresultresultresult',result)

				if isinstance(result, Iterable):
					for products, has_more in result:
						li_feed_vals = self.with_context(context).\
							_CreateFeedVals(products)
						# if has_more:kw['page'] += 1
						# else:
						kw['page'] = 0
						if kw.get('cron_service'):
							if len(li_feed_vals) < kw.get('page_size'):
								ChannelId.set_channel_date()

						return li_feed_vals, kw

					if kw.get('cron_service'):
						ChannelId.set_channel_date()
				# period_start = period_end

			elif kw.get('filter_type') == 'id':
				product_id = kw.get("object_id")
				li_feed_vals = self.get_product_using_product_id(
					product_id, ChannelId)
			else:
				raise UserError("All filter is not allowed for Exporting Products.")
		if not li_feed_vals:
			kw['message'] = 'No Products To Import In This Time Interval..'
		return li_feed_vals, kw
