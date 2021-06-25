# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ShipstationAccount(models.Model):
    _name = "shipstation.account"
    _inherit = "shipstation.connector"
    _description = "Shipstation Accounts"

    def _default_shipping_product(self):
        return self.env.ref('shipstation_shipping.shipping_charge', False)

    name = fields.Char(string="Name", required=True, copy=False)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.user.company_id)
    store_ids = fields.One2many('shipstation.store', 'shipstation_account_id', string="Stores")
    carrier_ids = fields.One2many('shipstation.carrier', 'shipstation_account_id', string="Carriers")
    warehouse_ids = fields.One2many('shipstation.warehouse', 'shipstation_account_id', string="Warehouses")
    shipping_product_id = fields.Many2one('product.product', string="Shipping Product", default=_default_shipping_product)
    state = fields.Selection([('draft', 'Inactive'), ('active', 'Active')], string="Status", default="draft")
    active = fields.Boolean(default=True)
    markup_rate = fields.Float(string="Markup Rate", default=0.0)
    weight_uom = fields.Selection([('pounds', 'Pounds (lbs)')], string="Weight UoM", default="pounds")

    _sql_constraints = [('api_keys_unique', 'unique(api_key, api_secret)', 'API keys must be unique per Shipstation Account')]

    def import_stores(self):
        self.ensure_one()
        res = self._import_stores()
        for data in res:
            vals = {
                'name': data.get('storeName'),
                'store_id': data.get('storeId'),
                'marketplace_name': data.get('marketplaceName'),
                'marketplace_id': data.get('marketplaceId'),
                'company_name': data.get('companyName'),
                'account_name': data.get('accountName') or '',
                'active': data.get('active'),
                'shipstation_account_id': self.id,
            }
            store = self.store_ids.filtered(lambda r: r.store_id == str(data.get('storeId')))
            if store:
                store.write(vals)
            else:
                store = self.store_ids.create(vals)

        return True

    def import_carriers(self):
        self.ensure_one()
        res = self._import_carriers()
        for data in res:
            vals = {
                'name': data.get('name'),
                'code': data.get('code'),
                'nick_name': data.get('nickname') or '',
                'is_primary': data.get('primary'),
                'is_requires_funded_account': data.get('requiresFundedAccount'),
                'account_number': data.get('accountNumber'),
                'shipping_provide_id': data.get('shippingProviderId'),
                'shipstation_account_id': self.id,
            }
            carrier = self.carrier_ids.filtered(lambda r: r.code == str(data.get('code')))
            if carrier:
                carrier.write(vals)
            else:
                carrier = self.carrier_ids.create(vals)
            carrier.import_services()
            carrier.import_packages()
        return True

    def import_warehouses(self):
        self.ensure_one()
        df_warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
        picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing'), ('warehouse_id', '=', df_warehouse.id)], limit=1)

        res = self._import_warehouses()

        for data in res:
            vals = {
                'name': data.get('warehouseName', ''),
                'is_default': data.get('isDefault', False),
                'shipstation_warehouse_id': data.get('warehouseId', ''),
                'shipstation_account_id': self.id,
            }
            warehouse = self.warehouse_ids.filtered(lambda r: r.shipstation_warehouse_id == str(data.get('warehouseId', '')))
            if warehouse:
                warehouse.write(vals)
            else:
                if data.get('isDefault', False):
                    vals.update({
                        'warehouse_id': df_warehouse.id,
                        'picking_type_id': picking_type.id,
                        'picking_state': 'done',
                    })
                warehouse = self.warehouse_ids.create(vals)
        return True

    def action_refresh(self):
        self.ensure_one()
        self.import_stores()
        self.import_carriers()
        self.import_warehouses()
        return True

    def action_confirm(self):
        self.ensure_one()
        self.state = 'active'
        self.action_refresh()
        return True

    def action_reset(self):
        self.ensure_one()
        self.state = 'draft'
        return True


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
