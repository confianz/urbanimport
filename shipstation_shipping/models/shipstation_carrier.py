# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ShipstationCarrier(models.Model):
    _name = "shipstation.carrier"
    _description = "Shipstation Carrier"

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", copy=False)
    nick_name = fields.Char("Nick Name")
    is_primary = fields.Boolean(string="Primary", copy=False)
    is_requires_funded_account = fields.Boolean(string="Requires Funded Account", copy=False)
    account_number = fields.Char(string="Account Number", copy=False)
    shipping_provide_id = fields.Char(string="Shipping Provider ID", copy=False)
    shipstation_account_id = fields.Many2one('shipstation.account', string="ShipStation Account")
    service_ids = fields.One2many('shipstation.service', 'carrier_id', string="Services")
    package_ids = fields.One2many('shipstation.package', 'carrier_id', string="Packages")
    active = fields.Boolean(default=True, copy=False)

    def import_services(self):
        self.ensure_one()
        res = self.shipstation_account_id._import_services(self.code)
        for data in res:
            vals = {
                'name': data.get('name'),
                'code': data.get('code'),
                'is_domestic': data.get('domestic'),
                'is_international': data.get('international'),
                'carrier_code': data.get('carrierCode'),
                'carrier_id': self.id,
            }
            service = self.service_ids.filtered(lambda r: r.code == str(data.get('code')))
            if service:
                service.write(vals)
            else:
                service = self.service_ids.create(vals)
                # creating and linking odoo shipping method with shipstation service
                if service:
                    deliver_carrier_id = self.env['delivery.carrier'].create({
                        'name': data.get('name'),
                        'delivery_type': 'shipstation',
                        'shipstation_id': self.shipstation_account_id.id,
                        'product_id': self.shipstation_account_id.shipping_product_id.id,
                        'margin': self.shipstation_account_id.markup_rate,
                        'shipstation_service_id': service.id,
                        'shipstation_service_code': data.get('code'),

                    })
        return True

    def import_packages(self):
        self.ensure_one()
        res = self.shipstation_account_id._import_packages(self.code)
        for data in res:
            vals = {
                'name': data.get('name'),
                'code': data.get('code'),
                'is_domestic': data.get('domestic'),
                'is_international': data.get('international'),
                'carrier_code': data.get('carrierCode'),
                'carrier_id': self.id,
            }
            package = self.package_ids.filtered(lambda r: r.code == str(data.get('code')))
            if package:
                package.write(vals)
            else:
                service = self.package_ids.create(vals)
        return True


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
