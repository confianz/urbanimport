# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class InternalTransferException(models.Model):
    _name = "internal.transfer.exception"
    _description = "Internal Transfer Exception"

    order_point_id = fields.Many2one(
        'stock.warehouse.orderpoint',
        string='Order Point')

    product_id = fields.Many2one(
        'product.product',
        string='Product')

    message = fields.Text(
        string="Message")

    warning_date = fields.Datetime(
        string='Warning Date')

    quantity = fields.Float(string='Quantity', digits='Product Quantity', default=0.0)
