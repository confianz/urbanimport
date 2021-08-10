# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2019-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
import base64  # file encode
import os
from PIL import Image
from io import BytesIO
import codecs
import html

from xml.etree import ElementTree as ET

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.odoo_multi_channel_sale.tools import _unescape, prettify

import logging
_logger = logging.getLogger(__name__)


class ExportTemplates(models.TransientModel):
	_inherit = "export.templates"

	def export_ebay_templates(self):
		return self.env['export.operation'].create(
			{
				'channel_id': self.channel_id.id,
				'operation': self.operation,
			}
		).export_button()


class ExportEbayTemplates(models.TransientModel):
	_name = "export.ebay.templates"
	_inherit = "export.templates"
	_description = "Export Ebay Templates"

	@api.model
	def export_now(self):
		for record in self:
			error_message = ""
			ebay_obj = object
			status = True
			template = self._context.get("template")
			api_obj = self.env["multi.channel.sale"]._get_api(
				self.channel_id, 'Trading')
			res = record._AssignProductDetails(template)
			if self.channel_id.debug == 'enable':
				_logger.info('Export Product Details ::: %r', res['Item'])
			if api_obj['status']:
				call_data = {
					'WarningLevel': 'High',
					'Item': res['Item']
				}
				try:
					response = api_obj['api'].execute(
						'AddFixedPriceItem', call_data)
					result_dict = response.dict()
					if self.channel_id.debug == 'enable':
						_logger.info('Ebay Response%r', result_dict)
					if result_dict['Ack'] in ['Success', 'Warning']:
						# tmp_msg = self.create_template_mapping_export(template_id, self.channel_id.id, result_dict['ItemID'])
						# var_mag = self.product_variant_mapping_export(template_id, self.channel_id.id, result_dict['ItemID'])
						# final_message = 'Product <b> %s </b>has been Successfully Exported to Ebay. Ebay Item id is %s </br>' % (_unescape(tmpl.name), result_dict['ItemID'])
						# if tmp_msg or var_mag:
						# final_message = '%s </br> %s'%(_unescape(tmp_msg),_unescape(var_mag))
						ebay_id = result_dict['ItemID']
						if self.channel_id.ebay_display_product_url:
							res = self.env['import.ebay.products'].get_product_data_using_product_id(
								ebay_id, self.channel_id)

							if res.get('result'):
								template.ebay_product_url = str(
									res.get('result')[0].get('ListingDetails').get('ViewItemURL'))
					else:
						error_message += 'Error in Exporting the Product to Ebay %s ' % result_dict[
							'Errors']['LongMessage']
				except Exception as e:
					error_message += 'Error in Exporting the Product (Odoo id= %s) to Ebay. </br> <b>Ebay Error Description :</b> </br>%s ' % (
						template.id, _unescape(e))
					status = False
			else:
				error_message = 'Error In Ebay Connection'

		if status:
			variants = []
			if template.product_variant_ids:
				for variant in template.product_variant_ids:
					attr_str = ",".join([attr_val.product_attribute_value_id.name
										 for attr_val in variant.product_template_attribute_value_ids])
					variants.append(dict(id=attr_str))
			ebay_obj = dict(id=ebay_id, variants=variants)
		return status, ebay_obj

	def update_now(self, **kw):
		status = False
		context = dict(self._context or {})
		api_obj = self.env["multi.channel.sale"]._get_api(
			self.channel_id, 'Trading')
		default_data = self.env[
			"multi.channel.sale"]._get_default_data(self.channel_id)
		if api_obj['status']:
			template = context["template"]
			status = self.update_product_to_ebay(
				template, kw.get('get_remote_id')(template))
		return status, kw

	@api.model
	def _return_policies(self, Obj):
		policy_return = {}
		try:
			description = self.escapeXMLErrors(Obj.ebay_return_description)
			policy_return = {
				'ReturnsAcceptedOption':  str(Obj.ebay_return_accepted_option),
				'Description': _unescape(description),
				'ReturnsWithinOption': str(Obj.ebay_return_within_option),
				'ShippingCostPaidByOption': str(Obj.ebay_return_accepted_option),
			}
		except Exception as e:
			_logger.info('Exception in return policies :::   %r', e)
		return policy_return

	@api.model
	def getEbayPictureDetails(self, temp_obj):
		picture_urls = {}
		urls = []
		url = ''
		url = self.getPictureURL(temp_obj)
		if url:
			urls.append(url)
		# if temp_obj.product_image_ids:
		# 	for image_id in temp_obj.product_image_ids:
		# 		url = self.getPictureURL(image_id)
		# 		if url:
		# 			urls.append(url)
		if not urls:
			urls.append(
				'http://thumbs2.ebaystatic.com/pict/1101893727856464_1.jpg')
		picture_urls.update({'PictureURL': urls})
		return picture_urls

	@api.model
	def getPNGImageData(self, img):
		""" Convert png image to jpg and return base64 jpg image data"""
		image = ''
		try:
			img = img.convert('RGB')
			path = "{}/../static/description/temporary_image.jpg".format(
				os.path.dirname(os.path.abspath(__file__)))
			img.save(path, 'JPEG')
			image = BytesIO(open(path, "rb").read())
		except Exception as e:
			_logger.info('Exception in converting png Image :::%r', e)
		return image

	@api.model
	def exportImageURL(self, img_url):
		image_data = False
		url = ""
		api_obj = self.env["multi.channel.sale"]._get_api(
			self.channel_id, 'Trading')
		image_data = self.env["multi.channel.sale"].read_website_image_url(
			img_url)
		context = self._context.copy() or {}
		if api_obj['status'] and image_data:
			try:
				image = BytesIO(base64.standard_b64decode(image_data))
				image_data = {'file': ('OdooExternalImage', image)}
				call_data = {
					"WarningLevel": "High",
					"PictureSet": 'Supersize',
					"PictureName": "dummy.png",
				}
				response = api_obj['api'].execute(
					'UploadSiteHostedPictures', call_data, files=image_data)
				url_dict = response.dict().get('SiteHostedPictureDetails')
				if url_dict:
					url = url_dict.get('FullURL')

			except Exception as e:
				_logger.info("## Error in exporting image %r", e)
		return url

	@api.model
	def getPictureURL(self, obj):
		url = ''
		try:
			if obj.image_1920:
				api_obj = self.env["multi.channel.sale"]._get_api(
					self.channel_id, 'Trading')
				image = BytesIO(base64.standard_b64decode(obj.image_1920))
				###########  checking the format of the image #######################
				img = Image.open(
					BytesIO(base64.b64decode(obj.image_1920))).convert('RGB')
				image_stream = BytesIO(codecs.decode(obj.image_1920, 'base64'))
				img = Image.open(image_stream)
				imageType = img.format.lower()
				if imageType == "png":
					image = self.getPNGImageData(img)
				image_data = {'file': ('OdooProductImage', image)}
				if api_obj['status']:
					name = self.escapeXMLErrors(obj.name)
					call_data = {
						"WarningLevel": "High",
						"PictureSet": 'Supersize',
						"PictureName": _unescape(name),
					}
					response = api_obj['api'].execute(
						'UploadSiteHostedPictures', call_data, files=image_data)
					url_dict = response.dict().get('SiteHostedPictureDetails')
					if url_dict:
						url = url_dict.get('FullURL')

		except Exception as e:
			_logger.info(' Exception in Exporting Image ::: %r', e)
		return url

	@api.model
	def parseHTML(self, text):
		odoo_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
		tree =  ET.fromstring(text)
		for image in tree.findall('.//img'):
			img_url = odoo_url+image.get('src')
			new_img_link = self.exportImageURL(img_url)
			image.set('src', new_img_link)
		return prettify(tree)

	@api.model
	def _GetShippingService(self, Obj):
		final_message = ''
		shipping_details = {}
		ShippingService = Obj.ebay_shipping_service.shipping_service
		if ShippingService:
			shippingpolicy = {
				'ShippingService': str(ShippingService),
				'ShippingServiceCost': float(Obj.ebay_shipping_cost),
				'ShippingServiceAdditionalCost':  float(Obj.ebay_shipping_additional_cost),
				'ShippingServicePriority': int(Obj.ebay_shipping_priority),
			}
			shipping_details = {
				'ShippingServiceOptions': shippingpolicy
			}
			#-----------------  for future use---------------------###

			# international_shippingpolicy = {
			# 			'ShippingService' : str(ShippingService),
			# 			'ShippingServiceCost' :float(config_obj.shipping_cost),
			# 			'ShippingServiceAdditionalCost':float(config_obj.ebay_shipping_additional_cost),
			# 			'ShippingServicePriority':int(config_obj.ebay_shipping_priority),
			# 			# 'ShipToLocation':'CA',
			# 		}
			# if config_obj.shipping_service.international_shipping:
			# 	shipping_details.update({'international_shippingServiceOption':international_shippingpolicy})
		return shipping_details

	@api.model
	def getVariationPictures(self, variants, template_obj):
		""" Create the dictionary for updating the images in  variants"""
		VariationSpecificName = ''
		pictures = []
		VariantionPictureSet = []
		picture_list = []
		for variant in variants:
			variant_attributes = variant.product_template_attribute_value_ids
			picture_url = self.getPictureURL(variant)
			if not picture_url:
				picture_url = 'http://thumbs2.ebaystatic.com/pict/1101893727856464_1.jpg'
			if len(template_obj.attribute_line_ids) == 1:
				for variant_attribute in variant_attributes:
					VariationSpecificName = _unescape(
						variant_attribute.attribute_id.name)
					VariantionPictureSet.append({
						'VariationSpecificValue':  _unescape(variant_attribute.name),
						'PictureURL': picture_url})
			if len(template_obj.attribute_line_ids) > 1:
				picture_list.append(picture_url)
		if len(template_obj.attribute_line_ids) > 1:
			VariationSpecificName = _unescape(
				template_obj.attribute_line_ids[0].attribute_id.name)
			if template_obj.attribute_line_ids[0].value_ids:
				VariationSpecificValue = _unescape(
					template_obj.attribute_line_ids[0].value_ids[0].name)
			VariantionPictureSet.append({
				'VariationSpecificValue': VariationSpecificValue,
				'PictureURL': picture_list
			})
		pictures.append(
			{'VariationSpecificName': VariationSpecificName,
			 'VariationSpecificPictureSet': VariantionPictureSet}
		)
		return pictures

	@api.model
	def get_MPN_and_BRAND(self, obj):
		if not obj.ebay_Brand:
			obj.ebay_Brand = 'Unbranded'
		if not obj.ebay_MPN:
			obj.ebay_MPN = self.channel_id.ebay_barcode_unavailable_text

		return {
			'mpn': self.escapeXMLErrors(obj.ebay_MPN),
			'brand': self.escapeXMLErrors(obj.ebay_Brand),
		}

	@api.model
	def get_UPC_and_EAN(self, obj):
		UPC = EAN = self.channel_id.ebay_barcode_unavailable_text
		if obj.wk_product_id_type and obj.barcode:
			if obj.wk_product_id_type == 'wk_upc':
				UPC = obj.barcode
			elif obj.wk_product_id_type == 'wk_ean':
				EAN = obj.barcode
		return {'UPC': UPC, 'EAN': EAN}

	@api.model
	def _get_variations(self, template_obj):
		Name = ''
		value = ''
		NameValueDict = []
		variation = []
		variations = {}
		name_value_specifics_list = []
		variants = template_obj.product_variant_ids
		attribute_lines = template_obj.attribute_line_ids
		final_message = ''
		status = True
		var_map_list = []
		variation_pictures = []
		name_value_specifics_set = {}
		variation_specifics = {}
		# Getting the properties of each variant and adding it to ebay Va
		if attribute_lines:
			pictures = []
			for variant in variants:
				variant_attributes = variant.product_template_attribute_value_ids
				name_value_lists = []
				for variant_attribute in variant_attributes:
					name_value_lists.append({'Name': _unescape(variant_attribute.attribute_id.name), 'Value': _unescape(
						variant_attribute.product_attribute_value_id.name)})
				variation_specifics = {'NameValueList': name_value_lists}
				ean_upc = self.get_UPC_and_EAN(variant)
				var_price = variant.with_context(
					dict(pricelist=self.channel_id.pricelist_name.id)).read(['price'])[0]
				qty = self.channel_id.get_quantity(variant)
				variation.append({
					# 'SKU':
					'StartPrice': float(var_price['price']),
					'Quantity': int(qty),
					'VariationSpecifics': variation_specifics,
					'VariationProductListingDetails': {'UPC': ean_upc.get('UPC'), 'EAN': ean_upc.get('EAN')}
				})
				if not variation:
					final_message = "No variant of the product %s has Quantity greater than Zero. Please Select the Qunatity first....." % _unescape(
						template_obj.name)
			for attribute_line in attribute_lines:
				values = []
				for value_id in attribute_line.value_ids:
					values.append(_unescape(value_id.name))
				name_value_specifics_list.append(
					{'Name': _unescape(attribute_line.attribute_id.name), 'Value': values})
			name_value_specifics_set = {
				'NameValueList': name_value_specifics_list}
			if self.channel_id.ebay_export_variant_images:
				pictures = self.getVariationPictures(variants, template_obj)
			variations = {	'VariationSpecificsSet': name_value_specifics_set,
						   'Variation': variation,
						   'Pictures': pictures
						   }
		return {'variations': variations, 'final_message': final_message, 'name_value_list': variation_specifics}

	@api.model
	def _get_ebay_primary_and_secondary_categories(self, category):
		ebay_primary_categ_id = ''
		ebay_secondary_categ_ids = ''
		if category.instance_id.channel == 'ebay':
			for categ_id in category.extra_category_ids:
				for channel_category_id in categ_id.channel_mapping_ids:
					primary_set = False
					if channel_category_id.ecom_store == 'ebay' and not primary_set:
						ebay_primary_categ_id = channel_category_id.store_category_id
						primary_set = True
					if primary_set:
						ebay_secondary_categ_ids += channel_category_id.store_category_id
		return {'ebay_primary_categ_id': ebay_primary_categ_id, 'ebay_secondary_categ_ids': ebay_secondary_categ_ids}

	@api.model
	def _get_ebay_category(self, template_obj):
		ebay_primary_categ_id = ''
		ebay_secondary_categ_ids = ''
		for category in template_obj.channel_category_ids:
			res = self._get_ebay_primary_and_secondary_categories(category)
			ebay_primary_categ_id = res.get('ebay_primary_categ_id')
			ebay_secondary_categ_ids = res.get('ebay_secondary_categ_ids')
		if not ebay_primary_categ_id:
			for category in template_obj.categ_id.channel_category_ids:
				res = self._get_ebay_primary_and_secondary_categories(category)
				ebay_primary_categ_id = res.get('ebay_primary_categ_id')
				ebay_secondary_categ_ids = res.get('ebay_secondary_categ_ids')
		if not ebay_primary_categ_id:
			if self.channel_id.ebay_default_category:
				ebay_primary_categ_id = self.channel_id.ebay_default_category.store_category_id
			else:
				raise UserError(
					"Error!!!. No ebay category specified for %s in Extra Categories(in Channel tab of the product) or Categories(in channel tab of the Product categories). Please specify the category for this product." % _unescape(template_obj.name))
		return {'ebay_categ_id': str(ebay_primary_categ_id),
				}

	@api.model
	def get_seller_profiles(self, Obj):
		seller_profiles = {}
		try:
			seller_profiles = {'SellerPaymentProfile': {
				'PaymentProfileID': str(Obj.ebay_existing_payment_policy.policy_id),
				# 'PaymentProfileName':str(self.channel_id.ebay_existing_payment_policy.name)
			},
				'SellerShippingProfile': {
				'ShippingProfileID': str(Obj.ebay_existing_shipping_policy.policy_id),
				# 'ShippingProfileName':str(self.channel_id.ebay_existing_shipping_policy.name)
			},
				'SellerReturnProfile': {
				'ReturnProfileID': str(Obj.ebay_existing_return_policy.policy_id),
				# 'ReturnProfileName':str(self.channel_id.ebay_existing_return_policy.name)
			}
			}
		except Exception as e:
			_logger.info('Exception in Seller profiles ::: %r', e)
		return seller_profiles

	@api.model
	def get_business_policies(self, template_obj):
		values = {}
		msg = ''
		try:
			if template_obj.ebay_overide_default_config:
				if template_obj.ebay_business_policies == 'existing':
					seller_profiles = self.get_seller_profiles(template_obj)
					values.update({'SellerProfiles': seller_profiles})
				else:
					payment_method = _unescape(
						self.channel_id.ebay_payment_method.name)
					if payment_method:
						values.update({'PaymentMethods': payment_method})
					paypal_email_address = _unescape(
						self.channel_id.paypal_email_address)
					if payment_method and payment_method == 'PayPal':
						values.update(
							{'PayPalEmailAddress': paypal_email_address})
					shipping = self._GetShippingService(template_obj)
					if shipping:
						values.update({'ShippingDetails': shipping})
					return_policy = self._return_policies(template_obj)
					if return_policy:
						values.update({'ReturnPolicy': return_policy})
			else:
				if self.channel_id.ebay_business_policies == 'existing':
					seller_profiles = self.get_seller_profiles(self.channel_id)
					values.update({'SellerProfiles': seller_profiles})
				else:
					payment_method = _unescape(
						self.channel_id.ebay_payment_method.name)
					if payment_method:
						values.update({'PaymentMethods': payment_method})
					paypal_email_address = _unescape(
						self.channel_id.paypal_email_address)
					if payment_method and payment_method == 'PayPal':
						values.update(
							{'PayPalEmailAddress': paypal_email_address})
					shipping = self._GetShippingService(self.channel_id)
					if shipping:
						values.update({'ShippingDetails': shipping})
					return_policy = self._return_policies(self.channel_id)
					if return_policy:
						values.update({'ReturnPolicy': return_policy})

			if not values.get('PaymentMethods'):
				raise ValidationError(
					'No payment policy specified. Please specify a payment policy in configuration.')
			if not values.get('ReturnPolicy'):
				raise ValidationError(
					'No return policy specified. Please specify a return policy in configuration.')
			if not values.get('ShippingDetails'):
				raise ValidationError(
					'No shipping policy specified. Please specify a shipping policy in configuration.')

		except Exception as e:
			_logger.info(
				' Exception in business policies ::: %r', _unescape(e))
		return values

	@api.model
	def escapeXMLErrors(self, string):
		"""Replace special characters "&", "<" and ">" to HTML-safe sequences"""
		if string:
			if "&" in string:
				string = string.replace("&", "&amp;")
			if "<" in string:
				string = string.replace("<", "&lt;")
			if ">" in string:
				string = string.replace(">", "&gt;")
		return string

	@api.model
	def getConditionID(self, template_obj):
		conditionID = 0
		if template_obj.ebay_overide_default_config and template_obj.ebay_condition_id:
			conditionID = template_obj.ebay_condition_id
		else:
			conditionID = self.channel_id.ebay_condition_id
		return int(conditionID)

	@api.model
	def _AssignProductDetails(self, template_obj):
		context = dict(self._context) or {}
		# temp_obj = self.env['product.template']
		# res_obj = self.env['res.users']
		message_status = ''
		Item = {}
		status = True
		final_message = ""
		variations = {}
		var_map_list = []
		shipping_service = {}
		ebay_category = ''
		picture_details = {}
		NameValueList = []
		if template_obj:
			template_id = template_obj.id
			# template_obj = temp_obj.browse(template_id)
			variants = template_obj.product_variant_ids
			country_code = self.channel_id.warehouse_id.partner_id.country_id.code
			postal_code = self.channel_id.warehouse_id.partner_id.zip
			if not country_code:
				raise ValidationError(
					'No country selected in the warehouse of the Channel. Please select the country first.')
			if not postal_code:
				raise ValidationError(
					'No Postal Code specified. Please enter the post code of your selected warehouse.')
			location = _unescape(self.channel_id.warehouse_id.partner_id.city)
			res_categ = self._get_ebay_category(template_obj)
			description = ""
			if template_obj.description_sale:
				description = (self.escapeXMLErrors(
					_unescape(template_obj.description_sale)))
				# print('descriptiondescriptiondescriptiondescription',description)
				description = description.encode(encoding='utf-8')
			if self.channel_id.ebay_use_html_description and template_obj.ebay_description_html:
				# description = '<![CDATA['+_unescape(template_obj.ebay_description_html)+']]>'
				parsed_desc = self.parseHTML(
					template_obj.ebay_description_html)
				description = (html.escape(parsed_desc).encode(
					"utf-8")).decode('iso-8859-1')
			if res_categ:
				ebay_category = res_categ['ebay_categ_id']
			name = self.escapeXMLErrors(template_obj.name)
			title = name[:80].encode(encoding='utf-8')
			upc_ean = self.get_UPC_and_EAN(template_obj)
			mpn_brand = self.get_MPN_and_BRAND(template_obj)
			listing_details = {
				'BrandMPN': {'MPN': mpn_brand.get('mpn'), 'Brand': mpn_brand.get('brand')},
				'EAN': upc_ean.get('EAN') or '',
				'UPC': upc_ean.get('UPC')
			}
			# print('listing_details',listing_details)
			tmp_price = template_obj.with_context(
				dict(pricelist=self.channel_id.pricelist_name.id)).read(['price'])[0]
			qty = self.channel_id.get_quantity(template_obj)

			conditionID = self.getConditionID(template_obj)
			Item = {
				'ListingType': 'FixedPriceItem',
				'Currency': str(self.channel_id.pricelist_name.currency_id.name),
				'Country': str(country_code),
				'PostalCode': str(postal_code),
				'ListingDuration': str(self.channel_id.ebay_listing_duration),
				'Description': description,
				'Title': _unescape(title),
				'PrimaryCategory': {'CategoryID': str(ebay_category)},
				'DispatchTimeMax': int(self.channel_id.ebay_dispatch_time_max),
				'ConditionID': conditionID,
				'SKU': self.escapeXMLErrors(template_obj.default_code) or "",
				'CategoryMappingAllowed': 'true',
				'ProductListingDetails': listing_details,
				'StartPrice': float(tmp_price['price']),
				'Quantity': int(qty),

			}
			if location:
				Item.update({'Location': location})
			picture_urls = self.getEbayPictureDetails(template_obj)
			if self.channel_id.debug == 'enable':
				_logger.info('Picture URLs  :::: %r', picture_urls)
			Item.update({'PictureDetails': picture_urls})
			business_policies = self.get_business_policies(template_obj)
			if template_obj.taxes_id:
				tax_id = template_obj.taxes_id[0]
				if tax_id.amount_type == 'percent':
					val = tax_id.amount
					vat_details = {
						'BusinessSeller': True,
						'VATPercent': val,
					}
					Item.update({'VATDetails': vat_details})
			if business_policies:
				Item.update(business_policies)
			NameValueList += [
				{'Name': 'Brand', 'Value': Item[
					'ProductListingDetails']['BrandMPN']['Brand']},
				{'Name': 'MPN', 'Value': Item[
					'ProductListingDetails']['BrandMPN']['MPN']}
			]
			if template_obj.use_ebay_specifics and template_obj.ebay_specifics:
				NameValueList += eval(_unescape(template_obj.ebay_specifics))
			else:
				channel_category_id = False
				for category in template_obj.channel_category_ids:
					if category.instance_id.channel == 'ebay':
						for categ_id in category.extra_category_ids:
							if categ_id.channel_mapping_ids:
								channel_category_id = categ_id.channel_mapping_ids[0]
				if channel_category_id and channel_category_id.ebay_category_specifics:
					NameValueList += eval(channel_category_id.ebay_category_specifics)

			if NameValueList:
				Item['ItemSpecifics'] = {'NameValueList': NameValueList}
			if len(variants) > 1:
				res_variation = self._get_variations(template_obj)
				if res_variation:
					variations = res_variation['variations']
					final_message = res_variation['final_message']
					Item.update({'Variations': variations})
				Item.update(
					{'ItemSpecifics': {'NameValueList': NameValueList}})
		return {'final_message': final_message,
				'status': status,
				'Item': Item}

	def update_product_to_ebay(self, template_id, store_id):
		status = False
		context = dict(self._context or {})
		MapObj = self.env['channel.template.mappings']
		api_obj = self.env["multi.channel.sale"]._get_api(
			self.channel_id, 'Trading')
		# res = self._AssignProductDetails(template_id)
		res = {}
		qty = self.channel_id.get_quantity(template_id)
		Item = {
			'Quantity': int(qty),
		}
		res['Item'] = Item
		if self.channel_id.debug == 'enable':
			_logger.info('Update Product Details :::   %r', res['Item'])
		if res and res['Item']:
			res['Item']['ItemID'] = store_id
			result_dict = {}
			if api_obj['status']:
				call_data = {
					# 'WarningLevel': 'High',
					# 'Item': res['Item']
				}
				try:
					response = api_obj['api'].execute(
						'ReviseFixedPriceItem', call_data)
					result_dict = response.dict()
					if result_dict['Ack'] in ['Success', 'Warning']:
						status = True

						if self.channel_id.ebay_display_product_url and not template_id.ebay_product_url:
							res = self.env['import.ebay.products'].get_product_data_using_product_id(
								store_id, self.channel_id)
							if res.get('result'):
								template_id.ebay_product_url = str(res.get('result')[0].get(
									'ListingDetails').get('ViewItemURL'))
				except Exception as e:
					status = False
					raise ValidationError(
						' Error In Updating the Product %s' % str(e))
		return status

	@api.model
	def update_ebay_quantity(self, mapping, prodQty):
		status = True
		ebayProdId = mapping.store_product_id
		ebayVarId = mapping.store_variant_id
		instanceObj = self.channel_id
		res_dict = self.env['import.ebay.products'].get_product_data_using_product_id(
			ebayProdId, instanceObj)
		result = res_dict.get('result')
		if isinstance(result, (list)):
			result = result[0]
		ebayQty = result.get('Quantity')
		# updatedQty = float(ebayQty) + prodQty
		Variations = {}
		if result.get('Variations'):
			variations = result.get('Variations').get('Variation')
			for variation in variations:
				attrString = self.env['import.ebay.products']._CreateAttributeString(
					variation)
				new_variation = {}
				if ebayVarId == attrString:
					updatedQty = float(variation.get('Quantity')) + prodQty
					new_variation.update({'Quantity': int(updatedQty)})
					new_variation.update(
						{'VariationSpecifics': variation.get('VariationSpecifics')})

		api_obj = self.env["multi.channel.sale"]._get_api(
			instanceObj, 'Trading')
		Item = {
			'Quantity': int(updatedQty),
			'ItemID': ebayProdId,
		}
		if Variations:
			Item.update({'Variations': {'Variation': [Variations]}})
		call_data = {
			'WarningLevel': 'High',
			'Item': Item
		}
		try:
			response = api_obj['api'].execute(
				'ReviseFixedPriceItem', call_data)
			result_dict = response.dict()
		except Exception as e:
			status = False
		return status
