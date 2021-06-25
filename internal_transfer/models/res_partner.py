# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _default_picking_type(self):
        type_obj = self.env['stock.picking.type']
        company_id = self.env.context.get('company_id') or self.env.user.company_id.id
        types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id.warehouse_type', '=', 'ocean')], limit=1)
        if not types:
            types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id', '=', False)])
        return types[:1]

    picking_type_id = fields.Many2one('stock.picking.type', 'Deliver To', required=True,
                                      default=_default_picking_type, \
                                      help="This will determine operation type of incoming shipment")


ResPartner()
