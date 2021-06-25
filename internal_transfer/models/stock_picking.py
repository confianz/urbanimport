# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    internal_transfer_id = fields.Many2one('internal.transfer.extension', "Internal Transfer Ref")
    transfer_done = fields.Boolean("transfer Done", default=False, copy=False)
    picking_type_code = fields.Selection([
        ('incoming', 'Vendors'),
        ('outgoing', 'Customers'),
        ('internal', 'Internal')], related='picking_type_id.code',
        readonly=True, store=True)
    warehouse_type = fields.Selection(related="picking_type_id.warehouse_id.warehouse_type", string="Warehouse Type")


#    def action_done(self):
#        res = super(StockPicking, self).action_done()
#        for rec in self:
#            if rec.internal_transfer_id:
#                if rec.internal_transfer_id and rec.picking_type_code == 'outgoing':
#                    rec.transfer_done = True
##                    rec.internal_transfer_id.receipt_picking_id.write({'state': 'done'})
##                    rec.internal_transfer_id.receipt_picking_id.move_line_ids.write({'state': 'done'})
#                    # rec.internal_transfer_id.receipt_picking_id.state = 'in_transit'
#                if rec.internal_transfer_id and rec.picking_type_code == 'incoming':
#                    print(rec.internal_transfer_id.delivery_picking_id.transfer_done)
#                    if not rec.internal_transfer_id.delivery_picking_id.transfer_done:
#                        raise UserError(
#                            _("Please complete entire Delivery Order corresponding to the Internal transfer - (%s)") %
#                            rec.internal_transfer_id.name)
#                    else:
#                        parent_id = rec.internal_transfer_id.delivery_picking_id.id
#                        while True:
#                            backorder = self.env['stock.picking'].search([('backorder_id', '=', parent_id)])
#                            if backorder and not backorder.transfer_done:
#                                raise UserError(
#                                    _("Please complete the Back order (Delivery) for the Internal transfer - (%s)") %
#                                    rec.internal_transfer_id.name)
#                            if backorder and backorder.transfer_done:
#                                parent_id = backorder.id
#                            if not backorder:
#                                break
#                rec.internal_transfer_id.write({'state': 'done'})
#        return res
#        
        
        
        
        
    def action_done(self):
        res = super(StockPicking, self).action_done()
        for rec in self:
            if rec.internal_transfer_id and rec.picking_type_code == 'outgoing':
                rec.transfer_done = True
#                rec.internal_transfer_id.receipt_picking_id.write({'in_transit': True})
#                rec.internal_transfer_id.receipt_picking_id.move_line_ids.write({'in_transit': True})
                # rec.internal_transfer_id.receipt_picking_id.state = 'in_transit'
            if rec.internal_transfer_id and rec.picking_type_code == 'incoming':
                if not rec.internal_transfer_id.delivery_picking_id.transfer_done:
                    raise UserError(
                        _("Please complete entire Delivery Order corresponding to the Internal transfer - (%s)") %
                            rec.internal_transfer_id.name)
                else:
                    parent_id = rec.internal_transfer_id.delivery_picking_id.id
                    while True:
                        backorder = self.env['stock.picking'].search([('backorder_id', '=', parent_id)])
                        if backorder and not backorder.transfer_done:
                            raise UserError(
                                _("Please complete the Back order (Delivery) for the Internal transfer - (%s)") %
                                    rec.internal_transfer_id.name)
                        if backorder and backorder.transfer_done:
                            parent_id = backorder.id
                        if not backorder:
                            break
                    rec.internal_transfer_id.write({'state': 'done'})
