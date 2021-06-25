# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta
from odoo.exceptions import Warning, UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    transaction_id = fields.Char(string='Transaction ID', copy=False)
    transaction_partner_id = fields.Many2one('res.partner', string='Authorized Customer', copy=False)
    payment_id = fields.Char(string='Payment ID', copy=False)
    extra_content = fields.Text('Customer Notes', copy=False)

    def write(self, vals):
        res = super(AccountPayment, self).write(vals)
        for rec in self:
            if rec.ref and rec.transaction_id and rec.payment_id and rec.state =='posted':
                invoice_ref = rec.ref
                invoice = self.env['account.move'].search(
                    [('name', '=', invoice_ref)])
                move_lines = rec.line_ids.filtered(
                    lambda line: line.account_internal_type in ('receivable', 'payable') and not line.reconciled)
                # move_lines = rec.mapped('move_line_ids').filtered(
                #     lambda line: not line.reconciled and line.credit > 0.0)
                for line in move_lines:
                    invoice.js_assign_outstanding_line(line.id)
        return res


    @api.model
    def default_get(self, fields):
        """updates the super method prepared dict of values with additional three fields
            triggered by pressing register payment button in invoice form"""

        res = super(AccountPayment, self).default_get(fields)
        invoice = self.env['account.move'].browse(self._context.get('active_id'))
        if invoice.transaction_id:
            res.update({'transaction_partner_id': invoice.partner_id.id, 'transaction_id': invoice.transaction_id,
                        'payment_id': invoice.payment_id or None})
        return res


    def _get_move_vals(self, journal=None):
        """ Return dict to create the payment move
        """
        journal = journal or self.journal_id

        move_vals = {
            'date': self.payment_date,
            'ref': self.communication or '',
            'company_id': self.company_id.id,
            'journal_id': journal.id,
        }

        name = False
        if self.move_name:
            names = self.move_name.split(self._get_move_name_transfer_separator())
            if self.payment_type == 'transfer':
                if journal == self.destination_journal_id and len(names) == 2:
                    name = names[1]
                elif journal == self.destination_journal_id and len(names) != 2:
                    # We are probably transforming a classical payment into a transfer
                    name = False
                else:
                    name = names[0]
            else:
                name = names[0]

        if name:
            move_vals['name'] = name
        return move_vals


class AccountMove(models.Model):
    _inherit = "account.move"

    message = fields.Text('Note')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
