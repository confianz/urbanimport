# -*- coding: utf-8 -*-

from odoo import models, fields,api


class ContainerConfig(models.TransientModel):
    _name = 'container.config'
    _description = "Container Configuration"
    _inherit ='res.config.settings'

    freight_account_id = fields.Many2one('account.account', string="Freight Account", config_parameter='freight_account_id', default='')
    customs_clearence_account_id = fields.Many2one('account.account', config_parameter='customs_clearence_account_id', string="Customs Clearence Account")




