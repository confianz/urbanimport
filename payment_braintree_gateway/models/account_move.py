# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import braintree
import logging


class AccountMove(models.Model):
    _inherit = "account.move"


    is_refund_braintree = fields.Boolean('Is Refunded', default=False, copy=False)

    _braintree_tx_void_allow_statuses = [
        braintree.Transaction.Status.Authorized,
        braintree.Transaction.Status.SettlementPending,
        braintree.Transaction.Status.SubmittedForSettlement
    ]
    def action_post(self):
        res = super(AccountMove, self).action_post()
        for invoice in self.filtered(lambda move: move.move_type == 'out_refund'):
            payments = invoice.mapped('transaction_ids.payment_id')
            move_lines = payments.line_ids.filtered(
                lambda line: line.account_internal_type in ('receivable', 'payable') and not line.reconciled)
            print('move_lines',move_lines)
            for line in move_lines:
                invoice.js_assign_outstanding_line(line.id)
        return res

    def create_and_open_payment(self):
        self.ensure_one()
        payment_link_wiz = self.env['payment.link.wizard'].create({
            'res_model': "account.move",
            'res_id': self.id,
            'amount': self.amount_residual,
            'amount_max': self.amount_residual,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            'description': self.payment_reference,
        })

        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': payment_link_wiz.link,
        }

    def button_cancel(self):
        payments =[]
        for invoice in self:
            payment = invoice._get_reconciled_payments()
            payments.append(payment)
            invoice.write({'transaction_ids': False})
        logging.error("paymentspaymentspayments-------------%s" % str(payments))
        for each in payments:
            if each.payment_transaction_id and each.payment_transaction_id.acquirer_id.provider == 'braintree' and each.state != 'cancel':
                transaction_ref = each.payment_transaction_id.acquirer_reference
                gateway = each.payment_transaction_id.acquirer_id.create_braintree_gateway()
                transaction = gateway.transaction.find(transaction_ref)
                tx_status = transaction.status
                logging.error("tx_statustx_status-------------%s" % str(tx_status))
                logging.error("acquirer_reference-------------%s" % str(each.payment_transaction_id.acquirer_reference))
                logging.error("self._braintree_tx_void_allow_statuses-------------%s" % str(self._braintree_tx_void_allow_statuses))
                if tx_status not in self._braintree_tx_void_allow_statuses:
                    logging.error("usererror------------")
                    raise UserError(_(
                        'Unable to cancel - %s, refund the settled invoices by creating a credit memo',
                        each.reconciled_invoice_ids[0].name))
        for each in payments:
            if each.payment_transaction_id and each.payment_transaction_id.acquirer_id.provider == 'braintree' and each.state != 'cancel':
                transaction_ref = each.payment_transaction_id.acquirer_reference
                gateway = each.payment_transaction_id.acquirer_id.create_braintree_gateway()
                result = gateway.transaction.void(transaction_ref)
                context = {}
                context.update({'from_invoice_braintree': True})
                each.action_draft()
                each.with_context(context).action_cancel()
                each.payment_transaction_id.write({
                    'state': 'cancel', 'payment_id': False,
                })
                if not result.is_success:
                    raise UserError(_(
                        'In order to cancel this invoice, refund the settled invoices by creating a credit memo \nError message - %s',
                        result.message))
        res = super(AccountMove, self).button_cancel()
        return res
