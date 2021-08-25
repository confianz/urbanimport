# coding: utf-8

import logging
import braintree
import pprint
import datetime

from odoo import api, fields, models, _
from odoo.exceptions import Warning, UserError

from odoo.addons.payment.models.payment_acquirer import _partner_split_name
from odoo.addons.payment.models.payment_acquirer import ValidationError

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def action_cancel(self):
        for each in self:
            from_invoice = self._context.get('from_invoice_braintree', False)
            if from_invoice:
                return super(AccountPayment, self).action_cancel()
            if each.payment_transaction_id and each.payment_transaction_id.acquirer_id.provider == 'braintree' and each.state != 'cancel':
                transaction_ref = each.payment_transaction_id.acquirer_reference
                gateway = each.payment_transaction_id.acquirer_id.create_braintree_gateway()
                result = gateway.transaction.void(transaction_ref)
                if not result.is_success:
                    raise UserError(_(
                        'In order to cancel this payment, refund the settled payment by creating a credit memo \nError message - %s',
                        result.message))
                each.payment_transaction_id.write({
                    'state': 'cancel', 'payment_id': False,
                })
        res = super(AccountPayment, self).action_cancel()
        return res


class PaymentAcquirerBraintree(models.Model):
    _inherit = 'payment.acquirer'

    # TODO: check for field that is required only if field is related to braintree only.
    provider = fields.Selection(selection_add=[('braintree', 'Braintree')], ondelete={'braintree': 'set default'})
    braintree_merchand_id = fields.Char('Braintree Merchant ID', groups='base.group_user')
    braintree_public_key = fields.Char('Braintree Public Key', groups='base.group_user')
    braintree_private_key = fields.Char('Braintree Private Key', groups='base.group_user')
    braintree_merchant_currency_ids = fields.One2many('braintree.merchant.currency', 'acquirer_id',
                                                      string='Braintree Merchant Currencies')

    def get_braintree_merchant_account(self, currency_id):
        res = self.env['braintree.merchant.currency'].sudo().search([('currency_id', '=', currency_id.id)])
        return res.merchant_account_id

    @api.model
    def _get_braintree_environment(self):
        environment = 'prod' if self.state == 'enabled' else 'test'
        if environment == 'prod':
            return braintree.Environment.Production
        return braintree.Environment.Sandbox

    def create_braintree_gateway(self):
        environment = self._get_braintree_environment()
        return braintree.BraintreeGateway(
            braintree.Configuration(
                environment,
                merchant_id=self.braintree_merchand_id,
                public_key=self.braintree_public_key,
                private_key=self.braintree_private_key
            )
        )

    def braintree_s2s_form_process(self, data):
        values = {
            'braintree_nonce': data.get('nonce'),
            'acquirer_id': int(data.get('acquirer_id')),
            'partner_id': int(data.get('partner_id')),
            'name': 'XXXXXXXXXXXX%s' % data.get('lastFour'),
        }
        pm_id = self.env['payment.token'].sudo().create(values)
        return pm_id


class TxBraintree(models.Model):
    _inherit = 'payment.transaction'

    _braintree_tx_settlement_statuses = [
        braintree.Transaction.Status.Settled,
        braintree.Transaction.Status.SettlementConfirmed,
        braintree.Transaction.Status.SettlementPending,
        braintree.Transaction.Status.Settling,
        braintree.Transaction.Status.SubmittedForSettlement
    ]

    _braintree_tx_pending_statuses = [
        braintree.Transaction.Status.Authorized,
        braintree.Transaction.Status.Authorizing,
    ]

    def _braintree_s2s_validate_tree(self, result):
        self.ensure_one()
        if self.state not in ("draft", "pending"):
            _logger.info('Braintree: trying to validate an already validated tx (ref %s)', self.reference)
            return True

        if result.is_success:
            tx_id = result.transaction.id
            tx_status = result.transaction.status
            self.write({'acquirer_reference': tx_id, 'date': fields.Datetime.now()})
            if tx_status in self._braintree_tx_settlement_statuses:
                self._set_transaction_done()
                self.execute_callback()
                if self.payment_token_id:
                    self.payment_token_id.verified = True
                return True
            if tx_status in self._braintree_tx_pending_statuses:
                self._set_transaction_pending()
                return True
        else:
            # result will be error message if the transcation is failed.
            error = result
            _logger.info("Error while doing transaction through braintree payment gateway %s", error)
            self._set_transaction_error(error)
            return False

    def braintree_s2s_do_transaction(self, **kwargs):
        self.ensure_one()
        gateway = self.acquirer_id.create_braintree_gateway()
        merchant_account = self.acquirer_id.get_braintree_merchant_account(self.currency_id)
        order_ref = self.reference or "ODOO-%s-%s" % (
            datetime.datetime.now().strftime('%y%m%d_%H%M%S'), self.partner_id.id)

        tx_values = {
            'amount': str(round(self.amount, 2)),
            'order_id': order_ref,
            'customer_id': self.payment_token_id.acquirer_ref,
            'merchant_account_id': merchant_account,
            'options': {
                'submit_for_settlement': True
            }
        }
        _logger.info("Sending values to braintree, values: %s", pprint.pformat(tx_values))
        try:
            result = gateway.transaction.sale(tx_values)
            return self._braintree_s2s_validate_tree(result)
        except Exception as e:
            _logger.info("Error while handling transaction for braintree transaction %s", e)


class PaymentTokenBraintree(models.Model):
    _inherit = 'payment.token'

    @api.model
    def braintree_create(self, values):
        if values.get('braintree_nonce') and not values.get('acquirer_ref'):
            partner = self.env['res.partner'].browse(values.get('partner_id'))
            payment_acquirer = self.env['payment.acquirer'].browse(values.get('acquirer_id'))
            gateway = payment_acquirer.create_braintree_gateway()
            result = gateway.customer.create({
                'first_name': '' if partner.is_company else _partner_split_name(partner.name)[0],
                'last_name': _partner_split_name(partner.name)[1],
                'email': partner.email or '',
                'phone': partner.mobile or partner.phone or '',
                'payment_method_nonce': values['braintree_nonce'],
                'credit_card': {
                    'options': {
                        'verify_card': True
                    }
                }
            })
            values.pop('braintree_nonce')
            if result.is_success:
                return {
                    'acquirer_ref': result.customer.id
                }
            else:
                _logger.info("Error while creating customer (id-%s) profile in braintree %s" % (partner.id, result))
                raise ValidationError(_('The Customer Profile creation in braintree failed.'))

        return values
