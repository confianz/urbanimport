# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError
import time


class AccountMove(models.Model):
    _inherit = "account.move"

    gateway_type = fields.Selection(selection_add=[('authorize', 'Authorize.net')], string='Payment Gateway')

    @api.model
    def aim_transaction_invoice(self, invoice_list=None, amount=None, card=None, cvv=None, expiry=None, extra=0.0,
                                invoice=None, message=None, surcharge=None,
                                account_name=None, routing_number=None,
                                account_number=None, bank_name=None,
                                eCheque_type=None, account_type=None,
                                ):
        """

        :param invoice_list: contains the invoices selected in the  website
        :param amount: the final payment amount
        :param card:
        :param cvv:
        :param expiry:
        :param extra: extra amount if exists
        :param order:
        :param message: reason for extra payment
        :return:
        """
        if account_number and routing_number:
            transaction_id_aim, error = self.env['authorizenet.api'].authorize_capture_cheque_transaction_aim(
                amount=amount,
                invoice=invoice, account_name=account_name,
                routing_number=routing_number,
                account_number=account_number, bank_name=bank_name,
                eCheque_type=eCheque_type, account_type=account_type)
        else:
            transaction_id_aim, error = self.env['authorizenet.api'].authorize_capture_transaction_aim(amount,
                                                                                                       str(card),
                                                                                                       str(cvv),
                                                                                                       str(expiry),
                                                                                                       invoice)
        if error:
            self.env['error.box'].create({

                'error_message': error,
                'order': self.env['account.move'].browse(int(invoice)).name
            })
            return False, error
        invoices = []
        for inv in invoice_list:
            invoice = self.browse(inv)
            invoice.write({'transaction_id': transaction_id_aim, 'transaction_date': fields.Datetime.now()})
            invoices.append(invoice.id)
            if invoice.type == 'out_refund' and invoice.transaction_id:
                invoice.write({'is_refund': True})
                if invoice.invoice_origin_id:
                    invoice.invoice_origin_id.write({'is_refund': True})
        invoice_id = self.browse(invoices[0])
        if invoice_id:
            Journal = self.env['account.journal'].search([('is_authorizenet', '=', True)], limit=1)
            payment_type = invoice_id and invoice_id.move_type in ('out_invoice', 'in_refund') and 'inbound' or 'outbound'
            payment_methods = payment_type == 'inbound' and Journal.inbound_payment_method_ids or Journal.outbound_payment_method_ids
            payment_method_id = payment_methods and payment_methods[0] or False
            register_payments = self.env['account.payment.register'].with_context({
                'active_model': 'account.move',
                'active_ids': invoices,
                'default_transaction_id': transaction_id_aim,
                'from_authorize': 'no_discount',

            }).create({
                'payment_date': fields.Date.context_today(self),
                'journal_id': Journal.id,
                'payment_method_id': payment_method_id and payment_method_id.id,
                # 'amount': float(amount) - extra
                # 'amount': float(amount)
            })

            payment = self.env['account.payment']
            for payment_vals in register_payments.get_payments_vals():
                payment += self.env['account.payment'].create(payment_vals)
            payment.write({'transaction_id': transaction_id_aim, 'amount': float(amount)})
            payment.post()
            if extra:
                partner = self.browse(invoices[0]).partner_id
                payment = self.env['account.payment'].create({
                    'amount': extra,
                    'payment_date': fields.Date.context_today(self),
                    'communication': invoice_id and invoice_id.move_type in (
                        'in_invoice', 'in_refund') and invoice_id.reference or invoice_id.name,
                    'partner_id': partner.commercial_partner_id and partner.commercial_partner_id.id,
                    'partner_type': invoice_id and invoice_id.move_type in (
                        'out_invoice', 'out_refund') and 'customer' or 'supplier',
                    'journal_id': Journal and Journal.id,
                    'payment_type': payment_type,
                    'payment_method_id': payment_method_id and payment_method_id.id,
                    'extra_content': message
                })

                payment.post()
                payment.write({'transaction_id': transaction_id_aim})
                move_lines = self.env['account.move.line'].search([('payment_id', 'in', payment.ids)])
                if move_lines:
                    move_lines[0].move_id.message = message
            # if card:
            #     default_account = self.env['ir.property'].get('property_account_receivable_id', 'res.partner')
            #     move_vals = payment._get_move_vals()
            #     # move_vals['type'] = 'entry'
            #     move_vals.update({'line_ids': [[0, 0, {
            #         'partner_id': payment.payment_type in ('inbound', 'outbound') and self.env[
            #             'res.partner']._find_accounting_partner(payment.partner_id).id or False,
            #         'debit': 0,
            #         'credit': surcharge and float(surcharge) or 0,
            #         'account_id': payment.journal_id.surcharge_account_id.id,
            #         'currency_id': payment.journal_id.currency_id.id,
            #         'journal_id': payment.journal_id.id
            #     }], [0, 0, {
            #         'partner_id': payment.payment_type in ('inbound', 'outbound') and self.env[
            #             'res.partner']._find_accounting_partner(payment.partner_id).id or False,
            #         'debit': surcharge and float(surcharge) or 0,
            #         'credit': 0,
            #         'account_id': default_account.id,
            #         'currency_id': payment.journal_id.currency_id.id,
            #         'journal_id': payment.journal_id.id
            #     }]]})
            #     move = self.env['account.move'].create(move_vals)
            #     # move.post()
            #     (move.line_ids.filtered(lambda r: not r.reconciled and r.account_id.internal_type in (
            #         'payable', 'receivable')) + payment.move_line_ids.filtered(
            #         lambda r: not r.reconciled and r.account_id.internal_type in ('payable', 'receivable'))).reconcile()
            Template = self.env.ref('payment_gateway_ui.email_template_payment_notifications_inside_invoice')
            if Template:
                Template.send_mail(invoice_id.id, force_send=False)
        return transaction_id_aim, error

    def register_card_payments(self):
        """
                register payments and make the invoice as paid
        """

        self.ensure_one()
        # self.action_invoice_open()
        Journal = self.env['account.journal'].search([('is_authorizenet', '=', True)], limit=1)
        if not Journal:
            raise UserError(_(
                'Error! \n Please Select The Authorize.net Journal.(Accounting->configuration->journal->Authorize.net Journal->True!'))
        payment_type = self.move_type in ('out_invoice', 'in_refund') and 'inbound' or 'outbound'
        payment_methods = payment_type == 'inbound' and Journal.inbound_payment_method_ids or Journal.outbound_payment_method_ids
        payment_method_id = payment_methods and payment_methods[0] or False
        context = {}  # dict(self._context)
        no_discount = self._context.get('card_transaction', False)
        context.update({'from_authorize': 'no_discount'})
        payment = self.env['account.payment'].with_context(context).create({
            # 'invoice_ids': [(6, 0, self.ids)],
            'amount': self._context.get('payment_amount', False) or self.amount_residual,
            # 'payment_date': fields.Date.context_today(self),
            'ref': self.move_type in ('in_invoice', 'in_refund') and self.reference or self.name,
            'partner_id': self.partner_id.commercial_partner_id and self.partner_id.commercial_partner_id.id,
            'partner_type': self.move_type in ('out_invoice', 'out_refund') and 'customer' or 'supplier',
            'journal_id': Journal and Journal.id,
            'payment_type': payment_type,
            'payment_method_id': payment_method_id and payment_method_id.id,
        })
        return payment

    def button_draft(self):
        """
        Void payment from Authourised.net
        @return: super
        """
        for invoice in self:
            if invoice.move_type == 'out_refund':
                return super(AccountMove, self).button_draft()

            payment = invoice._get_reconciled_payments()
            # print('button_draftbutton_draftbutton_draft', payment)
            # query = '''SELECT payment_id
            #                             FROM account_invoice_payment_rel WHERE invoice_id=%s'''
            # self.env.cr.execute(query, (invoice.id,))
            # payment = self.env.cr.fetchall()

            if invoice.payment_profile_id and not invoice.is_refund:
                for each in payment:
                    # each = self.env['account.payment'].browse(each)
                    response, msg, code = self.env['authorizenet.api'].void_payment(
                        invoice.commercial_partner_id.profile_id,
                        each.payment_id, each.transaction_id)
                    if not response:
                        raise UserError(
                            _(
                                "You cannot reset this order, try refund the settled invoices by creating a credit memo."))
            elif invoice.transaction_id and not invoice.is_refund:
                for each in payment:
                    # each = self.env['account.payment'].browse(each)
                    response, msg, code = self.env['authorizenet.api'].void_transaction_aim(each.transaction_id)
                    if not response:
                        raise UserError(
                            _(
                                "You cannot reset this order, try refund the settled invoices by creating a credit memo."))
            if invoice.is_refund and invoice.transaction_id_refund:
                refunded_ids = invoice.refund_invoice_ids.filtered(lambda inv: inv.state in ['open', 'paid'])
                if refunded_ids and sum(refunded_ids.mapped('amount_total')) < invoice.amount_total:
                    raise UserError(_("You cannot reset a partially refunded order"))
                return
            else:
                for each in payment:
                    if each.journal_id.is_authorizenet:
                        context = {}
                        context.update({'from_invoice': True})
                        each.with_context(context).action_cancel()
                res = super(AccountMove, self).button_draft()
                return res

    def button_cancel(self):
        """
        Void payment from Authourised.net
        @return: super
        """
        for invoice in self:
            if invoice.move_type == 'out_refund':
                return super(AccountMove, self).button_cancel()
            payment = invoice._get_reconciled_payments()
            # print('transaction_idstransaction_idstransaction_ids',payment)
            # query = '''SELECT payment_id
            #                             FROM account_invoice_payment_rel WHERE invoice_id=%s'''
            # self.env.cr.execute(query, (invoice.id,))
            # payment = self.env.cr.fetchall()
            Journal = self.env['account.journal'].search([('is_authorizenet', '=', True)], limit=1)
            for each in payment:
                # each = self.env['account.payment'].browse(each)
                # each = self.env['account.payment'].search([('move_reconciled', '=', True), ('id', 'in', each)])
                if each.payment_profile_id and not invoice.is_refund:
                    if each.state == 'posted' and each.journal_id == Journal:
                        response, msg, code = self.env['authorizenet.api'].void_payment(
                            invoice.commercial_partner_id.profile_id,
                            each.payment_profile_id, each.transaction_id)
                        if not response:
                            raise UserError(
                                _(
                                    "In order to cancel this order, refund the settled invoices by creating a credit memo."))
                elif each.transaction_id and not invoice.is_refund:
                    if each.state == 'posted' and each.journal_id == Journal:
                        response, msg, code = self.env['authorizenet.api'].void_transaction_aim(each.transaction_id)
                        if not response:
                            raise UserError(
                                _(
                                    "In order to cancel this order, refund the settled invoices by creating a credit memo."))
            if invoice.is_refund and invoice.transaction_id_refund:
                refunded_ids = invoice.refund_invoice_ids.filtered(lambda inv: inv.state in ['open', 'paid'])
                if refunded_ids and sum(refunded_ids.mapped('amount_total')) < invoice.amount_total:
                    raise UserError(_("You cannot cancel a partially refunded order"))
                return
            else:
                for each in payment:
                    if each.state == 'posted' and each.journal_id.is_authorizenet:
                        context = {}
                        context.update({'from_invoice': True})
                        each.with_context(context).action_cancel()
                invoice.write(
                    {'transaction_id': False, 'payment_profile_id': False, 'transaction_date': False, 'amount_gateway': False})
                res = super(AccountMove, self).button_cancel()
                return res

    @api.model
    def authorize_payment(self, invoice):
        """
        Authorize payment
        @param invoice: browse_record object of account.move
        @return: boolean value
        """
        authorize_obj = self.env['authorizenet.api']
        today = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        profile_id = invoice.partner_id._get_profile_id()
        new_id = authorize_obj.authorize_payment(profile_id, invoice.payment_profile_id, invoice.amount_total, invoice.origin)
        res = invoice.write(
            {'transaction_id': new_id, 'transaction_date': today, 'authorized_total': invoice.amount_total})
        return res


AccountMove()
