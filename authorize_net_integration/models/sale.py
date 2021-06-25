# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.api import Environment
import odoo, time
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import float_is_zero
from datetime import datetime, timedelta, date
import logging


class SaleOrder(models.Model):
    _inherit = "sale.order"

    gateway_type = fields.Selection(selection_add=[('authorize', 'Authorize.net')], string='Payment Gateway')

    def get_aim_transaction(self, amount=None, card=None, cvv=None, expiry=None, invoice=None, account_name=None,
                            routing_number=None,
                            account_number=None, bank_name=None,
                            eCheque_type=None, account_type=None, surcharge=None):
        """
        authorize AIM transaction
        :param amount:amount to authorize
        :param card:card number
        :param cvv:
        :param expiry:
        :param order:current order
        :return: transaction id and error message if exists
        """
        if account_number and routing_number:
            card_transaction = False
            transaction_id_aim, error = self.env['authorizenet.api'].authorize_capture_cheque_transaction_aim(
                amount=amount,
                invoice=invoice, account_name=account_name,
                routing_number=routing_number,
                account_number=account_number, bank_name=bank_name,
                eCheque_type=eCheque_type, account_type=account_type)
        else:
            card_transaction = True
            transaction_id_aim, error = self.env['authorizenet.api'].authorize_capture_transaction_aim(amount,
                                                                                                       str(card),
                                                                                                       str(cvv),
                                                                                                       str(expiry),
                                                                                                       invoice)
        if error:
            self.env['error.box'].create({

                'error_message': error,
                'order': self.env['account.move'].browse(int(invoice)).number
            })
            return False, error
        for cur_record in self:
            if transaction_id_aim:
                default_account = self.env['ir.property'].get('property_account_receivable_id', 'res.partner')
                record = self.env['payment.token.invoice'].search(
                    [('order_id', '=', cur_record.id),
                     ('state', '!=', 'expired'), ('model', '=', 'sale')], limit=1)
                current_inv_id = record and record.invoice_id
                current_inv_id.action_post()
                payment = current_inv_id.with_context(
                    {'payment_amount': amount, 'card_transaction': card_transaction}).register_card_payments()
                payment.post()
                payment.write({'transaction_id': transaction_id_aim})
                current_inv_id.write(
                    {'transaction_id': transaction_id_aim, 'amount_gateway': current_inv_id.amount_gateway + float(amount),
                     'transaction_date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                down_payment_amount = cur_record.down_payment_amount
                sale_update_vals = {'transaction_id': transaction_id_aim,
                                    'down_payment_amount': float(amount) + down_payment_amount,
                                    'transaction_date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)}
                if (float(amount) + down_payment_amount) >= cur_record.amount_total:
                    sale_update_vals['invoice_status'] = 'invoiced'
                cur_record.write(sale_update_vals)

                Template = self.env.ref(
                    'payment_gateway_ui.email_template_payment_notifications_inside_sales')
                if Template:
                    Template.send_mail(cur_record.id, force_send=False)
                return transaction_id_aim, False


SaleOrder()
