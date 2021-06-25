# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models,api,_


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def create(self, vals):
        res = super(PurchaseOrder, self).create(vals)
        if res and res.partner_id.picking_type_id:
            res.picking_type_id = res.partner_id.picking_type_id.id
        return res
        
    def write(self, vals):
        if vals.get('partner_id', False):
            partner = self.env['res.partner'].browse(vals.get('partner_id'))
            vals.update({'picking_type_id': partner.picking_type_id and partner.picking_type_id.id or self.picking_type_id.id})
        return super(PurchaseOrder, self).write(vals)
    
    


PurchaseOrder()
