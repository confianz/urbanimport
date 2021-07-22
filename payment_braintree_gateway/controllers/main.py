# -*- coding: utf-8 -*-
import logging
import braintree

from odoo import http
from odoo.http import request

from odoo.addons.payment.models.payment_acquirer import ValidationError

_logger = logging.getLogger(__name__)


class BraintreeController(http.Controller):

    @http.route(['/payment/braintree/get_token'], type='json', auth='public', website=True)
    def braintree_generate_client_token(self, **kwargs):
        order = request.website.sale_get_order()
        acquirer = request.env['payment.acquirer'].sudo().browse(kwargs['acquired_id'])
        merchant_account = acquirer.get_braintree_merchant_account(order.currency_id or acquirer.company_id.currency_id)
        if merchant_account:
            gateway = acquirer.create_braintree_gateway()
            try:
                client_token = gateway.client_token.generate()
                values = {
                    'braintree_client_token': client_token
                }
                return values
            except braintree.exceptions.authentication_error.AuthenticationError as e:
                _logger.error("Error while authenticating to braintree gateway. Please verify credentials.")
                raise ValidationError("Something went wrong while connecting to braintree gateway. Please try again later.")

        raise ValidationError ("Sorry!! This currency is not currently accepted by this site for this gateway. Please use different payment method.")

    @http.route(['/payment/braintree/s2s/create_json_3ds'], type='json', auth='public', csrf=False)
    def braintree_s2s_create_json_3ds(self, verify_validity=False, **kwargs):
        if not kwargs.get('partner_id'):
            kwargs = dict(kwargs, partner_id=request.env.user.partner_id.id)
        token = request.env['payment.acquirer'].browse(int(kwargs.get('acquirer_id'))).s2s_process(kwargs)

        if not token:
            res = {
                'result': False,
            }
            return res

        res = {
            'result': True,
            'id': token.id,
            'short_name': token.short_name,
            '3d_secure': False,
            'verified': False,
        }

        if verify_validity != False:
            token.validate()
            res['verified'] = token.verified

        return res
