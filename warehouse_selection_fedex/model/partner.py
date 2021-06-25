from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _get_address(self):

        return {
            'name': self.name,
            'company_name': self.parent_id and self.parent_id.name or self.name or '',
            'phone': self.phone or self.mobile or '',
            'address': self.street or '',
            'address1': self.street2 or '',
            'city': self.city or '',
            'state_code': self.state_id and self.state_id.code or '',
            'country_code': self.country_id and self.country_id.code or '',
            'country_name': self.country_id and self.country_id.name or '',
            'zip': self.zip or ''
        }


ResPartner()
