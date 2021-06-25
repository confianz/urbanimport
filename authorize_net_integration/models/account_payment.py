from odoo import models, fields, api, _
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError
import time


class account_payment(models.Model):
    _inherit = "account.payment"

    move_reconciled = fields.Boolean(compute="_get_move_reconciled", readonly=True, store =True)


    def action_cancel(self):
        for payment in self:
            from_invoice = self._context.get('from_invoice', False)
            if from_invoice:
                super(account_payment, payment).action_cancel()
                return super(account_payment, payment).action_cancel()
            if payment.journal_id.is_authorizenet == True:
                raise UserError(
                    _("In order to cancel this payment, refund or cancel the corresponding invoice"))
            else:
                super(account_payment, payment).action_cancel()
                return True
