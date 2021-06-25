from odoo import models, fields, api


class ProductProduct(models.Model):
    _inherit = "product.template"

    height = fields.Float("Height")
    width = fields.Float("Width")
    length = fields.Float("Length")

    @api.onchange('height', 'width', 'length')
    def calculate_volume(self):
        for rec in self:
            volume = rec.height * rec.width * rec.length
            volume_cubic_foot = volume and volume/1728 or 0.0
            rec.volume = volume_cubic_foot
