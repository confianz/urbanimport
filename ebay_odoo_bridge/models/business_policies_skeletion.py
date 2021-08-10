# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2019-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import models, fields


class BusinessPoliciesMappings(models.Model):
    _name = 'business.policies.mappings'
    _description = "Business policy Mappings"

    name = fields.Char(
        string='Profile Name',
        required=True,
    )
    policy_type = fields.Selection([
        ('PAYMENT', 'PAYMENT'),
        ('SHIPPING', 'SHIPPING'),
        ('RETURN_POLICY', 'RETURN_POLICY')],
        string='Policy Type',
        required=True,
    )
    policy_id = fields.Char(
        string='Policy ID',
        required=True,
    )
    description = fields.Text(
        string="Short Summary",
    )
    channel_id = fields.Many2one(
        comodel_name='multi.channel.sale',
        string='Instance',
        required=True,
        readonly=1,
    )
