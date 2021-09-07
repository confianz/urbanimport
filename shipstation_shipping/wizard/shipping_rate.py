# -*- encoding: utf-8 -*-

from odoo import api, fields, models


class ShippingRate(models.TransientModel):
    _name = "shipping.rate"
    _description = "ShipSation Shipping Rate"

    name = fields.Char(string="Service Name")
    code = fields.Char(string="Service Code")
    service_id = fields.Many2one('shipstation.service', string="Service")
    carrier_id = fields.Many2one(related="service_id.carrier_id", string="Carrier", store=False)
    package_id = fields.Many2one('shipstation.package', string="Package")
    cost = fields.Float(string="Shipping Charge")
    price = fields.Float(string="Markup Rate")
    delivery_carrier_id = fields.Many2one('choose.delivery.carrier', ondelete="cascade")

    def action_confirm(self):
        sale_order = self.delivery_carrier_id.order_id
        shipstation_account = self.carrier_id.shipstation_account_id
        if sale_order:
            sale_order._remove_delivery_line()
            # shipping_line = sale_order.order_line.filtered('is_delivery')[:1]
            # if shipping_line:
            #     shipping_line.write({
            #         'price_unit': self.price,
            #         'purchase_price': self.cost,
            #     })
            # else:
            shipping_line = sale_order.order_line.create({
                'product_id': shipstation_account.shipping_product_id.id,
                'product_uom_qty': 1,
                'price_unit': self.price,
                'purchase_price': self.cost,
                'is_delivery': True,
                'order_id': sale_order.id,
            })

            sale_order.write({
                'is_shipstation_shipping': True,
                'shipstation_package_id': self.package_id.id,
                'shipstation_service_id': self.service_id.id,
                'shipstation_carrier_id': self.carrier_id.id,
                'shipstation_account_id': shipstation_account.id,
            })
        return True

    def action_cancel(self):
        return {
            'name': "Update shipping cost" if self._context.get('carrier_recompute') else "Add a shipping method",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'choose.delivery.carrier',
            'res_id': self.delivery_carrier_id.id,
            'target': 'new',
        }


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
