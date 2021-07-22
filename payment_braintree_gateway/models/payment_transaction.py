# -*- encoding: utf-8 -*-

from odoo import api, fields, models


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _create_payment(self, add_payment_vals={}):
        ''' Create an account.payment record for the current payment.transaction.
        If the transaction is linked to some invoices, the reconciliation will be done automatically.
        :param add_payment_vals:    Optional additional values to be passed to the account.payment.create method.
        :return:                    An account.payment record.
        '''
        self.ensure_one()
        partner_id = self.partner_id.commercial_partner_id.id
        ref = self.reference
        if self.provider == 'braintree' and self.reference:
            invoice_ref = self.reference[:16]
            invoice = self.env['account.move'].search(
                [('name', '=', invoice_ref), ('company_id', '=', self.acquirer_id.company_id.id)], limit=1)
            if invoice:
                partner_id = invoice.partner_id.id
                if invoice.payment_state == 'not_paid' and not self.invoice_ids:
                    self.write({'invoice_ids': [(6, 0, invoice.ids)]})
                ref = invoice.payment_reference
        payment_vals = {
            'amount': self.amount,
            'payment_type': 'inbound' if self.amount > 0 else 'outbound',
            'currency_id': self.currency_id.id,
            'partner_id': partner_id,
            'partner_type': 'customer',
            'journal_id': self.acquirer_id.journal_id.id,
            'company_id': self.acquirer_id.company_id.id,
            'payment_method_id': self.env.ref('payment.account_payment_method_electronic_in').id,
            'payment_token_id': self.payment_token_id and self.payment_token_id.id or None,
            'payment_transaction_id': self.id,
            'ref': ref,
            **add_payment_vals,
        }
        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()

        # Track the payment to make a one2one.
        self.payment_id = payment

        if self.invoice_ids:
            self.invoice_ids.filtered(lambda move: move.state == 'draft')._post()

            (payment.line_ids + self.invoice_ids.line_ids) \
                .filtered(lambda line: line.account_id == payment.destination_account_id and not line.reconciled) \
                .reconcile()

        return payment

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
