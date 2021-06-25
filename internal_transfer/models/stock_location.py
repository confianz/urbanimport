# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _


class StockLocation(models.Model):
    _inherit = "stock.location"

    usage = fields.Selection(selection_add=[('internal_transit', 'Internal Transit')], ondelete={'internal_transit': 'cascade'})

StockLocation()