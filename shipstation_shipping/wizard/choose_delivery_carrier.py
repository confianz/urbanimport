# -*- encoding: utf-8 -*-

from odoo import api, fields, models


class ChooseDeliveryCarrier(models.TransientModel):
    _inherit = "choose.delivery.carrier"

    def _get_provider(self):
        # append provider list to the wizard type field (fedex,shipstation,fixed price etc)
        field_delivery_type = self.env.ref('delivery.field_delivery_carrier__delivery_type')
        provider_ids = field_delivery_type.selection_ids
        provider_list = []
        for provider in provider_ids:
            provider_list.append((provider.value, provider.name))

        return provider_list

    def _defalt_account(self):
        return self.env['shipstation.account'].search([('state', '=', 'active')], limit=1)

    carrier_id = fields.Many2one('delivery.carrier', required=False)
    delivery_type_id = fields.Selection(lambda self: self._get_provider(), string="Type")

    use_shipstation = fields.Boolean(string="Use Shipstation", default=False)
    shipstation_account_id = fields.Many2one('shipstation.account', string="ShipStation Account", default=_defalt_account)
    shipstation_carrier_id = fields.Many2one('shipstation.carrier', string="ShipStation Carrier")
    shipstation_service_id = fields.Many2one('shipstation.service', string="ShipStation Service")
    shipstation_package_id = fields.Many2one('shipstation.package', string="ShipStation Package")
    shipping_rate_ids = fields.One2many('shipping.rate', 'delivery_carrier_id', string="Shipping Rates")

    @api.onchange('delivery_type_id')
    def filter_by_provider(self):
        if self.delivery_type_id == 'shipstation':
            self.use_shipstation = True
        else:
            self.use_shipstation = False
        self.carrier_id = False

    @api.onchange('carrier_id')
    def set_shipstaion_config(self):
        if self.delivery_type_id == 'shipstation':
            if self.carrier_id:
                self.shipstation_account_id = self.carrier_id.shipstation_id.id
                self.shipstation_carrier_id = self.carrier_id.shipstation_service_id.carrier_id.id
            self.shipstation_service_id = self.carrier_id.shipstation_service_id.id
            self.shipstation_package_id = False

    def get_rate_from_shipstation(self):
        shipping_rates = [(5, 0, 0)]
        markup_rate = self.shipstation_account_id.markup_rate or 0.0
        sale_order = self.order_id
        carriers = self.shipstation_carrier_id or self.shipstation_carrier_id.search([('shipstation_account_id', '=', self.shipstation_account_id.id)])
        cost = 0
        for carrier in carriers:
            data = {
                'carrierCode': carrier.code,
                'serviceCode': self.shipstation_service_id.code or None,
                'packageCode': self.shipstation_package_id.code or None,
                'fromPostalCode': self.shipstation_account_id.company_id.partner_id.zip,
                'toCountry': sale_order.partner_shipping_id.country_id.code,
                'toPostalCode': sale_order.partner_shipping_id.zip,
                'toState': sale_order.partner_shipping_id.state_id.code or None,
                'toCity': sale_order.partner_shipping_id.city or None,
                'confirmation': 'delivery',
                'residential': False,
                'weight': {
                    'value': sale_order.weight,
                    'units': self.shipstation_account_id.weight_uom,
                },
            }

            res = self.shipstation_account_id._get_rates(data)

            services = {service.code: service.id for service in (self.shipstation_service_id or carrier.service_ids)}
            packages = {package.name: package.id for package in (self.shipstation_package_id or carrier.package_ids)}

            for rate in res:
                service_name = rate.get('serviceName', '').split('-')
                package_id = False
                if len(service_name) > 1:
                    package_id = packages.get(service_name[1].strip(), False)

                cost = rate.get('shipmentCost', 0.0) + rate.get('otherCost', 0.0)
                price = cost + cost * markup_rate / 100

                shipping_rates.append((0, 0, {
                    'name': rate.get('serviceName'),
                    'code': rate.get('serviceCode'),
                    'cost': cost,
                    'price': price,
                    'service_id': services.get(rate.get('serviceCode'), False),
                    'package_id': package_id,
                    'delivery_carrier_id': self.id,
                }))

        self.write({'shipping_rate_ids': shipping_rates})
        if self._context.get('shipstation', False):
            return {'price': cost}
        return {
            'name': "Update shipping cost" if self._context.get('carrier_recompute') else "Add a shipping method",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'choose.delivery.carrier',
            'res_id': self.id,
            'target': 'new',
        }


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
