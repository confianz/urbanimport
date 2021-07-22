# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    refund_method = fields.Selection(
        [('refund', 'Create a credit note'), ('cancel', 'Full Refund'),
         ('modify', 'Full refund and new draft invoice')],
        default='refund', string='Credit Method', required=True,
        help='Choose how you want to credit this invoice. You cannot Modify and Cancel if the invoice is already reconciled')

    def reverse_moves(self):
        context = dict(self._context or {})
        res = super(AccountMoveReversal, self).reverse_moves()
        if self.refund_method == 'refund':
            invoice = self.env['account.move'].browse(context.get('active_id'))
            refunded_invoice = self.env['account.move'].browse(res.get('res_id', False))
            payment = invoice._get_reconciled_payments()
            if invoice and res.get('res_id', False) and refunded_invoice.move_type == 'out_refund':
                for each in payment:
                    if each.payment_transaction_id and each.payment_transaction_id.acquirer_id.provider == 'braintree' and each.state != 'cancel':
                        transaction_ref = each.payment_transaction_id.acquirer_reference
                        gateway = each.payment_transaction_id.acquirer_id.create_braintree_gateway()
                        result = gateway.transaction.refund(transaction_ref)
                        if not result.is_success:
                            raise UserError(_(
                                'Payment is not processed yet, Try after some time or try to cancel the invoice \nError message - %s',
                                result.message))
                        else:
                            tx_id = result.transaction.id
                            invoice.write({'is_refund_braintree': True})
                            acquirer = self.env['payment.acquirer'].search(
                                [('provider', '=', 'braintree'),
                                 ('company_id', '=', self.env.company.id)])
                            refunded_invoice.action_post()
                            Journal = acquirer.journal_id
                            payment_method_id = self.env.ref('payment.account_payment_method_electronic_in')
                            payment_vals = {'journal_id': Journal.id,
                                            'payment_type': 'outbound',
                                            'partner_id': invoice.partner_id.id,
                                            'company_id': acquirer.company_id.id,
                                            'payment_method_id': payment_method_id and payment_method_id.id,
                                            'amount': each.amount}
                            payment = self.env['account.payment'].with_context({
                                'active_model': 'account.move',
                                'active_ids': [refunded_invoice.id],

                            }).create(payment_vals)

                            trans_vals = {
                                'invoice_ids': [(6, 0, [refunded_invoice.id])],
                                'amount': payment.amount,
                                # 'reference': payment.ref,
                                'acquirer_reference': tx_id,
                                'currency_id': payment.currency_id.id,
                                'partner_id': payment.partner_id.id,
                                'partner_country_id': payment.partner_id.country_id.id,
                                'payment_token_id': payment.payment_token_id and payment.payment_token_id.id or False,
                                'acquirer_id': acquirer.id,
                                'payment_id': payment.id,
                                'state': 'done',
                            }
                            transaction = self.env['payment.transaction'].create(trans_vals)
                            refunded_invoice.write({'transaction_ids': [(3, 0, [transaction.id])]})
                            payment.payment_transaction_id = transaction
                            payment.action_post()
                            refunded_invoice.action_post()


            else:
                return res
        return res
