# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################

from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def multichannel_sync_quantity(self, pick_details):
        channel_list = self._context.get('channel_list', [])
        channel_list.append('ebay')
        return super(
            StockMove, self.with_context(channel_list=channel_list)
        ).multichannel_sync_quantity(pick_details)
