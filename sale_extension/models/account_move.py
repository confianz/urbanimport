# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import braintree
import logging


class AccountMove(models.Model):
    _inherit = "account.move"

    def button_cancel(self):
        self.button_draft()
        res = super(AccountMove, self).button_cancel()
        return res
