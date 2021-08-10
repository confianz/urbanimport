# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2019-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

import logging
_logger = logging.getLogger(__name__)


class ImportEbayCategories(models.TransientModel):
	_name = "import.ebay.categories"
	_description = "Import Ebay Caetegories"
	_output_selector = "CategoryCount,CategoryArray.Category.CategoryName,CategoryArray.Category.CategoryParentID,CategoryArray.Category.CategoryLevel,CategoryArray.Category.CategoryID"

	@api.model
	def _FetchEbayCategoryByIdList(self, api):
		context = dict(self._context or {})

		if 'categ_list' not in context:
			categ_list = []
		else:
			categ_list = context['categ_list']
		try:
			callData = {
				'CatgegorySiteID': context['ebay_cat_site_id'],
				'CategoryID': context['ebay_category_id'],
				'LevelLimit': context['levellimit'],

			}
			result_dict = api.execute('GetCategoryInfo', callData).dict()
			if context["channel_id"].debug == 'enable':
				_logger.info(
					'--------------Category Response------------%r', result_dict)
			if result_dict['Ack'] == 'Success':
					if result_dict.get('CategoryArray'):
						category = result_dict.get(
							'CategoryArray').get('Category')
						if category.get('CategoryParentID') != '-1':
							categ_list.append(category)
							self.with_context(ebay_category_id=category.get(
								'CategoryParentID'), categ_list=categ_list)._FetchEbayCategoryByIdList(api)
						else:
							category['CategoryParentID'] = ''
						return categ_list.append(category)
		except Exception as e:
			if context["channel_id"].debug == 'enable':
				_logger.info(
					'----------Exception in Fetching Categories-------------------%r', e)
		finally:
			return categ_list


	@api.model
	def _FetchEbayCategories(self, api):
		message = ""
		status = True
		result = False
		total = 0
		context = dict(self._context or {})
		# print('responseresponseresponseresponseresponseresponseresponseresponseresponseresponse')

		try:
			callData = {
				'DetailLevel': 'ReturnAll',
				'CategorySiteID': context['ebay_cat_site_id'],
				'LevelLimit': context['levellimit'],
			}
			if context.get('ebay_root_category_id'):
				callData['CategoryParent'] = str(
					context['ebay_root_category_id'])
			# print('contextcontextcontextcontext',context)
			# print('callDatacallDatacallDatacallDatacallDatacallData',callData)
			# print(test)
			response = api.execute('GetCategories', callData)
			result_dict = response.dict()
			if context["channel_id"].debug == 'enable':
				_logger.info(
					'--------------Category Response------------%r', result_dict)
			if result_dict['Ack'] == 'Success':
				if result_dict.get('CategoryArray'):
					result = result_dict.get('CategoryArray').get('Category')
					total = result_dict.get('CategoryCount')
				else:
					status = False
					message = "No Child Categories found for this Category."
			else:
				message = message + 'STATUS : %s <br>' % result_dict['Ack']
				message = message + \
					'ErrorCode : %s <br>' % result_dict['Errors']['ErrorCode']
				message = message + 'ShortMessage : %s <br>' % result_dict[
					'Errors']['ShortMessage']
				message = message + "LongMessage: %s <br>" % result_dict[
					'Errors']['LongMessage']
				status = False
		except Exception as e:
			message = "Error in Fetching Categories: %s" % e
			status = False
			_logger.info(
				'----------Exception in Fetching Categories-------------------%r', e)
		return {'status': status, 'message': message, 'result': result, 'total': total}

	@api.model
	def _CreateFeedVals(self, categories):
		feed_list = []
		context = dict(self._context or {})
		if context.get('channel_id'):
			ChannelID = context['channel_id']
		for ebay_categ in categories:
			vals = {
				'name': ebay_categ['CategoryName'],
				'store_id': ebay_categ['CategoryID'],
				'channel_id': ChannelID.id,
				'channel': 'ebay'
			}
			if ebay_categ['CategoryID'] != ebay_categ['CategoryParentID']:
				vals['parent_id'] = ebay_categ['CategoryParentID']
			if ebay_categ.get('LeafCategory'):
				vals['leaf_category'] = True
			feed_list.append(vals)
		return feed_list

	def import_now(self, **kw):
		feed_list = []
		context = dict(self._context or {})
		ChannelId = kw.get("channel_id")
		context["channel_id"] = ChannelId
		kw.update(page_size=float("inf"))
		MultiChannel = self.env["multi.channel.sale"]
		# print('import_nowimport_nowimport_nowimport_nowimport_nowimport_now',kw)
		if kw.get('filter_type') == 'date_range':
			raise UserError("Date Range filter is not allowed for Exporting Categories.")
		if kw.get('filter_type') == 'all':
			api_obj = MultiChannel._get_api(
				ChannelId, 'Trading')
			if api_obj['status']:
				DefaultData = MultiChannel._get_default_data(ChannelId)
				context['ebay_cat_site_id'] = DefaultData['data']['ebay_cat_site_id']
				context['levellimit'] = kw.get('limit', '1')
				if kw.get('ebay_category'):
					context['ebay_root_category_id'] = kw.get('ebay_category')
				FetchedEbayCategories = self.with_context(
					context)._FetchEbayCategories(api_obj['api'])
				if FetchedEbayCategories['status']:
					feed_list = self.with_context(context)._CreateFeedVals(
						FetchedEbayCategories['result'])
		if kw.get('filter_type') == 'id':
			api_obj = MultiChannel._get_api(
				ChannelId, 'Shopping')
			if api_obj['status']:
				DefaultData = MultiChannel._get_default_data(ChannelId)
				context['ebay_cat_site_id'] = DefaultData['data']['ebay_cat_site_id']
				context['ebay_category_id'] = kw.get('object_id')
				context['levellimit'] = kw.get('limit', '1')
			FetchEbayCategoryList = self.with_context(
				context)._FetchEbayCategoryByIdList(api_obj['api'])
			feed_list = self.with_context(context)._CreateFeedVals(
					FetchEbayCategoryList)
			if 'TemplateCall' in context:
				self.env['category.feed']._create_feeds(feed_list)
				return True
		return feed_list, kw
