from odoo import models, fields, api, _
import ast
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    incoming_buffer_days = fields.Integer('Buffer days - Incoming Shipment', default=1)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        incoming_buffer_days = self.env['ir.config_parameter'].sudo().get_param('incoming_buffer_days')
        res.update(
            incoming_buffer_days=incoming_buffer_days,
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('incoming_buffer_days', self.incoming_buffer_days)
