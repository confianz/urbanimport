from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    company_contact_id = fields.Many2one('res.partner',"Contact Name")


ResPartner()
