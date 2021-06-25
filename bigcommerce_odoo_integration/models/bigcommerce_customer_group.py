# -*- coding: utf-8 -*-
from odoo import models, fields


class BigcommerceCustomerGroup(models.Model):
    _name = 'bigcommerce.customer.group'
    _description = 'Bigcommerce Customer Group'

    name = fields.Char(string="Name")
    customer_group_id = fields.Char(string="Bigcommerce Customer group id")
    bc_store_id = fields.Many2one(string='Bigcommerce Store')
