# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class StockInternalTransfer(models.TransientModel):
    _name = 'stock.internal.move'

    destination_location_id = fields.Many2one('stock.location', string="Internal Location")
    

#    @api.multi
    def stock_transfer(self):
        '''
        To move receiving stock to an internal location 
        '''
        picking = self.env['stock.picking'].browse(self.env.context.get('active_id', False))
        if picking and picking.picking_type_id and picking.picking_type_id.code == 'incoming':
            picking_type = self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1)
            for move in picking.move_lines:
                values = {
                        'product_id': move.product_id.id,
                        'partner_id': move.picking_id.partner_id.id,
                        'origin': move.picking_id and move.picking_id.origin or False,
                        'product_uom': move.product_uom.id,
                        'price_unit': move.price_unit,
                        'product_uom_qty': move.product_uom_qty,
                        'picking_type_id': picking_type.id,
                        'location_id': move.location_dest_id.id,
                        'location_dest_id': self.destination_location_id.id,
                        'name': move.product_id.name,
                        'quantity_done': move.quantity_done,
                }
                new_move = self.env['stock.move'].create(values)
                new_move._action_confirm()
                new_move._action_assign()
                new_move._action_done()
                if new_move.state != 'done':
                    raise UserError(_('Currently mentioned quantities are not available at the location !'))
            picking.update({'is_transfer_done': True})

StockInternalTransfer()
