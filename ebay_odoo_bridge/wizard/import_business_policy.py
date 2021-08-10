# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2019-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)


class EbayImportBusinessPolicies(models.TransientModel):
    _name = "ebay.import.business.policies"
    _description = "Import Ebay Business Poilicies"

    @api.model
    def _FetchEbayBusinessPolicies(self, api, ChannelID):
        message = ""
        status = True
        result = []
        try:
            callData = {
                'ShowSellerProfilePreferences': True,
                'ShowSellerPaymentPreferences': True
            }
            response = api.execute('GetUserPreferences', callData)
            result_dict = response.dict()
            if ChannelID.debug == 'enable':
                _logger.info(
                    '----------Result Dictionary-----------%r', result_dict)
            if result_dict['Ack'] == 'Success':
                if result_dict.get('SellerProfilePreferences'):
                    result = result_dict.get('SellerProfilePreferences').get(
                        'SupportedSellerProfiles').get('SupportedSellerProfile')
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
            message = "Error in Fetching Business Policies: %s" % e
            _logger.info(
                '--------Error in Fetching Business Policies---------%r', e)
            status = False
        return {'status': status, 'message': message, 'result': result}

    @api.model
    def CreateBusinessPoliciesValsList(self, result, ChannelID):
        EbayPolicyList = []
        for record in result:
            values = {
                'name': record.get('ProfileName'),
                'policy_type': record.get('ProfileType'),
                'policy_id': record.get('ProfileID'),
                'description': record.get('ShortSummary'),
                'channel_id': ChannelID.id
            }
            EbayPolicyList.append(values)
        return EbayPolicyList

    @api.model
    def import_now(self, **kw):
        data_list = []
        context = dict(self._context or {})
        kw.update(page_size=float("inf"))
        # FIXME pagination in future
        ChannelID = kw.get("channel_id")
        api_obj = self.env["multi.channel.sale"]._get_api(ChannelID, 'Trading')
        if api_obj['status']:
            business_policies = self._FetchEbayBusinessPolicies(
                api_obj['api'], ChannelID)
            if business_policies['status']:
                data_list = self.with_context(context).CreateBusinessPoliciesValsList(
                    business_policies['result'], ChannelID)
        return data_list, kw
