# -*- coding: utf-8 -*-

import logging

from odoo import http
from odoo.http import request


class Shipstation(http.Controller):
    @http.route("/shipstation/webhook/notification/<int:account>", type="json", auth="public")
    def shipstation_webhook_notification(self, account=None, **kwargs):
        data = request.jsonrequest and request.jsonrequest or {}
        logging.error(data)
        SaleOrder = request.env['sale.order'].sudo()
        if data.get('resource_type') == 'SHIP_NOTIFY':
            SaleOrder.update_order_from_shipstation_webhook(data.get('resource_url'), account)
            return 'SUCCESS'

        return 'FAILURE'


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
