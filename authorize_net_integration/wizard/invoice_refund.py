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
        # print('self.refund_method', self.refund_method)
        if self.refund_method == 'refund':
            invoice = self.env['account.move'].browse(context.get('active_id'))
            paid_amount = invoice.amount_total - invoice.amount_residual
            authorize_amount = invoice.amount_gateway
            # print('authorize_amountpaid_amount', paid_amount, authorize_amount)
            refunded_invoice = self.env['account.move'].browse(res.get('res_id', False))
            if authorize_amount != paid_amount:
                refunded_invoice.action_post()
                return res
            payment_records = self.env['payment.token.invoice'].search(
                [('invoice_id', '=', invoice.id), ('model', '=', 'sale')])
            if invoice.state != 'open':
                for rec in payment_records:
                    rec.state = 'expired'

            query = '''SELECT payment_id FROM account_invoice_payment_rel WHERE invoice_id=%s'''
            self.env.cr.execute(query, (invoice.id,))
            payment = self.env.cr.fetchall()
            # print('payment', payment)

            if invoice and invoice.payment_profile_id and res.get('res_id', False):
                refunded_invoice.write({'payment_id': invoice.payment_profile_id, 'invoice_origin_id': invoice.id,
                                        'commercial_partner_id': invoice.commercial_partner_id.id,
                                        'transaction_date': invoice.transaction_date,
                                        'transaction_id': invoice.transaction_id})
                if refunded_invoice.move_type == 'out_refund':
                    for each in payment:
                        each = self.env['account.payment'].browse(each)
                        # print('each', each.payment_profile_id, each.transaction_id, each.amount, invoice.name)
                        t_id = self.env['authorizenet.api'].refund_payment(invoice.commercial_partner_id.profile_id,
                                                                           each.payment_id,
                                                                           each.transaction_id, each.amount,
                                                                           invoice.name)
                        # print('payment_idt_id', t_id)
                        if t_id:
                            invoice.write({'is_refund': True, 'transaction_id_refund': t_id})
                            if invoice.invoice_origin_id:
                                invoice.invoice_origin_id.write({'is_refund': True, 'transaction_id_refund': t_id})
                            Journal = self.env['account.journal'].search([('is_authorizenet', '=', True)], limit=1)
                            payment_type = refunded_invoice and refunded_invoice.move_type in (
                                'out_invoice', 'in_refund') and 'inbound' or 'outbound'
                            payment_methods = payment_type == 'inbound' and Journal.inbound_payment_method_ids or Journal.outbound_payment_method_ids
                            payment_method_id = payment_methods and payment_methods[0] or False
                            # print('payment_method_id', payment_method_id)
                            # print('Journal', Journal)
                            # print('refund_amount', each.amount)
                            refunded_invoice.action_post()
                            # print('refunded_invoice', refunded_invoice)

                            payment_vals = {'payment_date': fields.Date.context_today(self),
                                            'journal_id': Journal.id,
                                            'payment_method_id': payment_method_id and payment_method_id.id,
                                            'amount': each.amount}
                            payment = self.env['account.payment'].with_context({
                                'active_model': 'account.move',
                                'active_ids': [refunded_invoice.id],
                                'default_transaction_id': t_id,
                                'from_authorize': 'no_discount',

                            }).create(payment_vals)
                            payment.write({'transaction_id': t_id})
                            payment.post()
                        else:
                            raise UserError(
                                _("Payment is not processed yet, Try after some time or try to cancel the invoice"))
            elif invoice and invoice.transaction_id and res.get('res_id', False):
                refunded_invoice.write({'transaction_id': invoice.transaction_id, 'invoice_origin_id': invoice.id,
                                        'commercial_partner_id': invoice.commercial_partner_id.id,
                                        'transaction_date': invoice.transaction_date})
                if refunded_invoice.move_type == 'out_refund':
                    for each in payment:
                        each = self.env['account.payment'].browse(each)
                        # print('each', each.payment_id, each.transaction_id, each.amount, invoice.name)
                        t_id = self.env['authorizenet.api'].refund_payment_aim(each.transaction_id, each.amount,
                                                                               invoice.name)
                        # print('transaction_idt_id', t_id)
                        if t_id:
                            invoice.write({'is_refund': True, 'transaction_id_refund': t_id})
                            if invoice.invoice_origin_id:
                                invoice.invoice_origin_id.write({'is_refund': True, 'transaction_id_refund': t_id})
                            Journal = self.env['account.journal'].search([('is_authorizenet', '=', True)], limit=1)
                            payment_type = refunded_invoice and refunded_invoice.move_type in (
                                'out_invoice', 'in_refund') and 'inbound' or 'outbound'
                            payment_methods = payment_type == 'inbound' and Journal.inbound_payment_method_ids or Journal.outbound_payment_method_ids
                            payment_method_id = payment_methods and payment_methods[0] or False
                            # print('payment_method_id', payment_method_id)
                            # print('Journal', Journal)
                            # print('refund_amount', each.amount)
                            refunded_invoice.action_post()
                            # print('refunded_invoice', refunded_invoice)

                            payment_vals = {'payment_date': fields.Date.context_today(self),
                                            'journal_id': Journal.id,
                                            'payment_method_id': payment_method_id and payment_method_id.id,
                                            'amount': each.amount}
                            payment = self.env['account.payment'].with_context({
                                'active_model': 'account.move',
                                'active_ids': [refunded_invoice.id],
                                'default_transaction_id': t_id,
                                'from_authorize': 'no_discount',

                            }).create(payment_vals)
                            payment.write({'transaction_id': t_id})
                            payment.post()
                        else:
                            raise UserError(
                                _("Payment is not processed yet, Try after some time or try to cancel the invoice"))
            else:
                return res
        return res
