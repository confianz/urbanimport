# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class StockRule(models.Model):

    _inherit = 'stock.rule'

    def _prepare_purchase_order(self, company_id, origins,values):
        res = super(StockRule, self)._prepare_purchase_order(company_id, origins,values)
        values = values[0]
        partner = values['supplier'].name
        if partner and partner.picking_type_id:
            res.update({'picking_type_id': partner.picking_type_id.id})
        return res

    def _make_po_get_domain(self, company_id, values, partner):
        res = super(StockRule, self)._make_po_get_domain(company_id, values, partner)
        if res and partner.picking_type_id:
            for domain in res:
                if domain[0] == 'picking_type_id':
                    res = (
                        ('partner_id', '=', partner.id),
                        ('state', '=', 'draft'),
                        ('picking_type_id', '=', partner.picking_type_id.id),
                        ('company_id', '=', company_id.id),
                    )
                    break
            return res
        return res

