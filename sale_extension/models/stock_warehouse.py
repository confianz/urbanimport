
from odoo import models, fields, api, _


class Warehouse(models.Model):
    _inherit = "stock.warehouse"

    state_ids = fields.One2many('res.country.state', 'warehouse_id', string='States')


class CountryState(models.Model):
    _inherit = 'res.country.state'

    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
