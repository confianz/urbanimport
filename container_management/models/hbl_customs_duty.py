# -*- coding: utf-8 -*-

from odoo import models, fields,api
from datetime import datetime



class HblCustoms(models.Model):
    _name = 'hbl.customs.duty'
    _description = "HBL Customs"

    date = fields.Date(string="Date", default=datetime.today())
    hbl_line_id = fields.Many2one('container.line', string="Container Line")
    hbl_id = fields.Many2one('house.bill.lading', string="HBL", related="hbl_line_id.hbl_id")
    product_id = fields.Many2one('product.product', string = "Product", related="hbl_line_id.purchase_line.product_id")
    vendor_id = fields.Many2one('res.partner', string = "Vendor", related="hbl_line_id.purchase_line.partner_id")
    order_id = fields.Many2one('purchase.order', string='Origin', related="hbl_line_id.purchase_line.order_id")
    hts_ids = fields.Many2many('product.hts.code', string="HTS Code")
    quantity = fields.Float(string="Quantity", digits='Product Unit of Measure')
    unit_price = fields.Float(string="Unit Price", digits='Product Price')
    duty_percentage = fields.Float(string="Duty Percentage")
    price_total = fields.Float('Purchase Total', compute="compute_total_customs_duty")
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self:self.env.user.company_id.currency_id)


    @api.depends('quantity','unit_price')
    def compute_total_customs_duty(self):
        """
        Compute the total duty percentage for each purchase line.
        there is an extra duty for some vendors.If the 'extra_duty'
        field's value is true,then we use a duty perc(0.288 most probably)
        for each 144 qtys
        """
        for rec in self:
            total = 0.0
            extra_duty = 0.0
            price_total = rec.quantity * rec.unit_price
#                total = (price_total * duty_percentage)/100
            rec.price_total = price_total
#            for hts in rec.hts_ids:
#                if hts.extra_duty_applicable:
#                    extra_duty += ((rec.quantity/hts.quantity) * hts.extra_duty)
#            rec.total = total + extra_duty

        return True

HblCustoms()

