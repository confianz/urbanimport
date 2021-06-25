# -*- coding: utf-8 -*-

from odoo import models, fields,api

class ProductHts(models.Model):
    _name = 'product.hts.code'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Product HTS Code"

    code = fields.Char(string='HTS Code', tracking=True)
    percentage = fields.Float(string='Percentage', tracking=True)
    name = fields.Char(string='Name',compute='_compute_name', store=True)
    description = fields.Char(string="Description")
    revise_date = fields.Date(string='Revise Date')
    extra_duty_applicable = fields.Boolean(string="Extra Duty Applicable")
    extra_duty = fields.Float(string="Extra Duty", digits='Product Price', tracking = True )
    quantity = fields.Float(string="No. of Units for which extra duty is applicable", digits='Product Unit of Measure', tracking=True)


#    @api.depends('code','percentage','description','extra_duty','quantity')
#    def _compute_name(self):
#        for record in self:
#            if record.code:
#                record.name = "%s(%s%%) %s" % (record.code, record.percentage, record.description or "") \
#                 if not record.extra_duty_applicable else '%s(%s %% with $%s per %s units) %s' % (record.code, record.percentage, record.extra_duty, int(record.quantity), record.description or "")

    @api.depends('code','percentage','description','extra_duty','quantity')
    def _compute_name(self):
        for record in self:
            name=""
            if record.code:
                name = "%s(%s%%) %s" % (record.code, record.percentage, record.description or "") \
                 if not record.extra_duty_applicable else '%s(%s %% with $%s per %s units) %s' % (record.code, record.percentage, record.extra_duty, int(record.quantity), record.description or "")
            record.name = name

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name), ('name', operator, name)]
        hts_code = self.search(domain + args, limit=limit)
        return hts_code.name_get()

ProductHts()

