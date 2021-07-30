# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
from datetime import datetime
from werkzeug.exceptions import Forbidden, NotFound

from odoo import fields, http, SUPERUSER_ID, tools, _
from odoo.http import request
from odoo.addons.base.models.ir_qweb_fields import nl2br
from odoo.addons.http_routing.models.ir_http import slug
from odoo.addons.payment.controllers.portal import PaymentProcessing
from odoo.addons.website.controllers.main import QueryURL
from odoo.addons.website.models.ir_http import sitemap_qs2dom
from odoo.exceptions import ValidationError
from odoo.addons.portal.controllers.portal import _build_url_w_params
from odoo.addons.website.controllers.main import Website
from odoo.addons.website_form.controllers.main import WebsiteForm
from odoo.osv import expression

_logger = logging.getLogger(__name__)
from odoo.addons.website_sale.controllers.main import WebsiteSale


class CustomWebsiteSale(WebsiteSale):
    @http.route([
        '''/shop''',
        '''/shop/page/<int:page>''',
        '''/shop/category/<model("product.public.category"):category>''',
        '''/shop/category/<model("product.public.category"):category>/page/<int:page>'''
    ], type='http', auth="public", website=True, )
    def shop(self, page=0, category=None, search='', ppg=False, **post):
        allowed_groups = request.env['website.menu'].sudo().search(
            [('website_id', '=', request.website.id), ('url', 'ilike', '/shop')],
            limit=1).group_ids
        user_groups = request.env['res.users'].browse(request.uid).groups_id
        if allowed_groups and user_groups:
            check = any(item in allowed_groups.ids for item in user_groups.ids)
            if not check:
                raise NotFound()
        res = super(CustomWebsiteSale, self).shop(page=page, category=category, search=search, ppg=ppg, **post)
        return res

    @http.route(['/shop/cart'], type='http', auth="public", website=True, sitemap=False)
    def cart(self, access_token=None, revive='', **post):
        allowed_groups = request.env['website.menu'].sudo().search(
            [('website_id', '=', request.website.id), ('url', 'ilike', '/shop')],
            limit=1).group_ids
        user_groups = request.env['res.users'].browse(request.uid).groups_id
        if allowed_groups and user_groups:
            check = any(item in allowed_groups.ids for item in user_groups.ids)
            if not check:
                raise NotFound()
        res = super(CustomWebsiteSale, self).cart(access_token=access_token, revive=revive, **post)
        return res
