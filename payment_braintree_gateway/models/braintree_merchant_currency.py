import logging
_logger = logging.getLogger(__name__)
from odoo import api, fields, models, _


class BraintreeMerchantCurrencies(models.Model):

    _name = 'braintree.merchant.currency'
    _description = 'Braintree Merchant Currency'

    _sql_constraints = [
        ('braintree_merchant_currency_uniq', 'unique(acquirer_id, currency_id)',
         'You can not have same currency for different merchant accounts!!'),
    ]

    merchant_account_id = fields.Char(required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    acquirer_id = fields.Many2one('payment.acquirer', string='Acquirer', required=True)
