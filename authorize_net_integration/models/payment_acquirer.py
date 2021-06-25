# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class PaymentAcquirer(models.Model):
    _inherit = "payment.acquirer"

    def _check_required_if_provider(self):
        """ If the field has 'required_if_provider="<provider>"' attribute, then it
        required if record.provider is <provider>. """
        return
