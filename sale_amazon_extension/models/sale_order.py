# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_amazon_order = fields.Boolean("Is Amazon order")
    
    def set_delivery_line(self, carrier, amount):
        self.carrier_id = carrier.id
        for pick in self.picking_ids:
            pick.carrier_id = carrier.id
        if self.is_amazon_order:
#            self.carrier_id = carrier.id
#            for pick in self.picking_ids:
#                pick.carrier_id = carrier.id
            return
        return super(SaleOrder, self).set_delivery_line(carrier, amount)

    def action_open_delivery_wizard(self):
        view_id = self.env.ref('delivery.choose_delivery_carrier_view_form').id
        if self.env.context.get('carrier_recompute'):
            name = _('Update shipping cost')
            carrier = self.carrier_id
        else:
            name = _('Add a shipping method')
            carrier = self.partner_id.property_delivery_carrier_id
        amazon_order = self.is_amazon_order
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'choose.delivery.carrier',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_carrier_id': carrier.id,
                'amazon_order': amazon_order,
            }
        }

