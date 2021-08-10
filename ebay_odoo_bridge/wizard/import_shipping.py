# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2019-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import api, fields, models, _
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)


class ImportEbayShippingMethods(models.TransientModel):
    _name = "import.ebay.shipping.methods"
    _description = "Import Ebay Shipping Methods"

    @api.model
    def _CreateOdooShippingFeedVals(self, shipping_methods, ChannelID):
        FeedValsList = []
        for shipping_method in shipping_methods:
            if isinstance(shipping_method, (dict)):
                shipping_method = [shipping_method]
            shipping_method = shipping_method[0]
            if shipping_method.get('ShippingService') and shipping_method.get('ValidForSellingFlow', 'true'):
                values = {
                    'channel_id': ChannelID.id,
                    'channel': 'ebay',
                    'name': shipping_method['ShippingService']
                }
                if shipping_method.get('ShippingServiceID'):
                    values.update(
                        {'store_id': shipping_method['ShippingServiceID']})
                if shipping_method.get('InternationalService'):
                    values.update({'is_international': True})
                else:
                    values.update({'is_international': False})
                if shipping_method.get('ShippingCarrier'):
                    values.update(
                        {'shipping_carrier': shipping_method['ShippingCarrier'][0]})
                else:
                    values.update({'shipping_carrier': 'Other'})
                FeedValsList.append(values)
        return FeedValsList

    @api.model
    def _FetchEbayShippingDetails(self, api):
        message = ""
        status = True
        result = False
        try:
            result = []
            callData = {
                'DetailName': 'ShippingServiceDetails',
            }
            response = api.execute('GeteBayDetails', callData)
            result_dict = response.dict()
            if result_dict['Ack'] == 'Success':
                result = result_dict['ShippingServiceDetails']
                if type(result_dict) == list:
                    result.extend(result_dict['ShippingServiceDetails'])
                else:
                    result.append(result_dict['ShippingServiceDetails'])
            else:
                message = message + 'STATUS : %s <br>' % result_dict['Ack']
                message = message + \
                    'ErrorCode : %s <br>' % result_dict['Errors']['ErrorCode']
                message = message + \
                    'ShortMessage : %s <br>' % result_dict[
                        'Errors']['ShortMessage']
                message = message + \
                    "LongMessage: %s <br>" % result_dict[
                        'Errors']['LongMessage']
                status = False
        except Exception as e:
            message = "Error in Fetching Shipping Methods: %s" % e
            status = False
        return {'status': status, 'message': message, 'result': result}

    @api.model
    def import_now(self, **kw):
        data_list = []
        ChannelID = kw.get("channel_id")
        context = dict(self._context or {})
        kw.update(page_size=float("inf"))
        # FIXME pagination in future
        api_obj = self.env["multi.channel.sale"]._get_api(ChannelID, 'Trading')
        if api_obj['status']:
            shipping_methods = self.with_context(
                context)._FetchEbayShippingDetails(api_obj['api'])
            if shipping_methods['status']:
                data_list = self.with_context(context)._CreateOdooShippingFeedVals(
                    shipping_methods['result'], ChannelID)
        return data_list, kw
