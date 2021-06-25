# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    reference = fields.Char(string="Reference")
    #    warehouse_id = fields.Many2one('stock.warehouse', string="Pick From", required=True)
    picking_type_id = fields.Many2one('stock.picking.type', string="Picking Type", required=True, domain="['|','&',('sequence_code','in',('PICK','IN','QC')),('warehouse_id.code','=','WH1'),'&',('sequence_code','=','OUT'),('warehouse_id.code','=','WH2')]")

    picking_ids = fields.One2many(
        'stock.picking', 'batch_id', string='Transfers',
        domain="[('company_id', '=', company_id), ('state', 'not in', ('done', 'cancel')), ('picking_type_id', '=', picking_type_id)]",
        help='List of transfers associated to this batch')
    picking_type_id_code = fields.Char('Picking Type Code', related='picking_type_id.sequence_code', readonly=True)

    @api.model
    def create(self, vals):
        res = super(StockPickingBatch, self).create(vals)
        if not self.reference:
            res.reference = '%s/%s/%s' % (res.picking_type_id.warehouse_id.code, date.today(), res.name.split('/')[1])
        return res

    def name_get (self):
        result = []
        for rec in self:
            name = rec.reference or rec.name
            result.append((rec.id, name))
        return result
        
    @api.onchange('picking_type_id')
    def _onchange_pic_type(self):
        if self.picking_type_id:
            self.picking_ids = False

    def print_picking(self):
        pickings = self.mapped('picking_ids')
        if not pickings:
            raise UserError(_('Please add atleast one picking.'))
        return self.env.ref('stock_pick_batch.action_report_pic_batch').report_action(self)

    def done(self):
        self._check_company()
        pickings = self.mapped('picking_ids').filtered(lambda picking: picking.state not in ('cancel', 'done'))
        if any(picking.state not in ('assigned') for picking in pickings):
            raise UserError(_(
                'Some transfers are still waiting for goods. Please check or force their availability before setting this batch to done.'))
        for picking in pickings:
            picking.message_post(
                body="<b>%s:</b> %s <a href=#id=%s&view_type=form&model=stock.picking.batch>%s</a>" % (
                    _("Transferred by"),
                    _("Batch Transfer"),
                    picking.batch_id.id,
                    picking.batch_id.name))

        picking_to_backorder = self.env['stock.picking']
        picking_without_qty_done = self.env['stock.picking']
        picking_without_carrier = self.env['stock.picking']
        for picking in pickings:
            if not picking.carrier_id and picking.picking_type_id != picking.picking_type_id.warehouse_id.pack_type_id:
                picking_without_carrier |= picking
            elif all([x.qty_done == 0.0 for x in picking.move_line_ids]):
                # If no lots when needed, raise error
                picking_type = picking.picking_type_id
                if (picking_type.use_create_lots or picking_type.use_existing_lots):
                    for ml in picking.move_line_ids:
                        if ml.product_id.tracking != 'none':
                            raise UserError(_('Some products require lots/serial numbers.'))
                # set qty done for QC step.           
                if picking_type == picking.picking_type_id.warehouse_id.pack_type_id and picking.state == 'assigned':
                    for line in picking.move_line_ids:
                        line.qty_done = line.product_uom_qty
                    picking.button_validate()
                else:
                    # Check if we need to set some qty done.
                    picking_without_qty_done |= picking
            elif picking._check_backorder():
                picking_to_backorder |= picking
            else:
                picking.action_done()
        if picking_without_carrier:
            raise UserError(
                _('Please configure a Carrier before validating %s' % ','.join(picking_without_carrier.mapped('name'))))
        if picking_without_qty_done:
            view = self.env.ref('stock.view_immediate_transfer')
            wiz = self.env['stock.immediate.transfer'].create({
                'pick_ids': [(4, p.id) for p in picking_without_qty_done],
                'pick_to_backorder_ids': [(4, p.id) for p in picking_to_backorder],
            })
            return {
                'name': _('Immediate Transfer?'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'stock.immediate.transfer',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': wiz.id,
                'context': self.env.context,
            }
        if picking_to_backorder:
            return picking_to_backorder.action_generate_backorder_wizard()
        # Change the state only if there is no other action (= wizard) waiting.
        self.write({'state': 'done'})
        return True
        
        
class StockPicking(models.Model):
    _inherit = "stock.picking"
    
    customer_po_number = fields.Char(string="Customer PO Number", related="sale_id.client_order_ref")
    dealer = fields.Many2one('res.partner', string="Dealer", related="sale_id.partner_id")
    product_sku = fields.Char(string="Product SKU", compute="_compute_product_sku")
    qty_order = fields.Char(string="Quantity", compute="_compute_product_sku")

    def _compute_product_sku(self):
        for pick in self:
            move_ids = pick.move_ids_without_package.filtered(lambda r : r.product_id.default_code)
            internal_reference = move_ids.mapped('product_id').mapped('default_code')
            pick.product_sku = ','.join(internal_reference)
            quantity = pick.move_ids_without_package.mapped('product_uom_qty')
            pick.qty_order = ','.join(['%d'%(qty) for qty in quantity])

