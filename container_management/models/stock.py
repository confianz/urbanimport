# -*- coding: utf-8 -*-

from odoo import api, fields, models,_
from odoo.exceptions import ValidationError

class StockMove(models.Model):
    _inherit = "stock.move"

    container_ids = fields.Many2many('container.container', string="Container No.", states={'done': [('readonly', True)]})
    mhbl_ids = fields.Many2many('master.house.bill.lading', string="Master Bill Of Lading")
    container_line_id = fields.Many2one('container.line','Container Lines')
#    purchase_line_id = fields.Many2one('purchase.order.line', string="PO Line")


#class StockMove(models.Model):
#    _inherit = "stock.move.line"

#    container_line_id = fields.Many2one('container.line','Container Lines')


StockMove()

class StockPicking(models.Model):
    _inherit = "stock.picking"

    mbl_id = fields.Many2one('master.house.bill.lading', string="Master Bill Of Lading", readonly=True, states={'draft': [('readonly', False)]})
    container_id = fields.Many2one('container.container', string="Container", readonly=True, states={'draft': [('readonly', False)]})
    po_id = fields.Many2one('purchase.order',string="Purchase Order", readonly=True, states={'draft': [('readonly', False)]})
    warehouse_code = fields.Char(related="picking_type_id.warehouse_id.code", string="Warehouse code")
    carrier = fields.Char(string="Carrier")
    bill_of_lading = fields.Char(string="Bill of Lading")
    direct_transfer_done = fields.Boolean(string="Done Direct Transfer")
#    is_transfer_done = fields.Boolean(stirng= "Internal Transfer Done", copy=False)

#Inheriting this mode because client will do direct internal transfer from oc/stock to wrehouse
#without using 'Transfer to warehouse button' in container
    @api.constrains('container_id','mbl_id','po_id','move_lines')
    def  constarint_container(self):
        if self.container_id and self.mbl_id and self.po_id:
            product_ids = self.container_id.container_lines.filtered(lambda rec:rec.po_id.id==self.po_id.id).mapped('purchase_line.product_id').ids
            container_line_ids = self.container_id.mapped('container_lines').ids
            for index,line in enumerate(self.move_lines):
                if line.product_id.id not in product_ids:
                    raise ValidationError('You cannot add new product %s'% line.product_id.display_name)
                if line.container_line_id.id not in container_line_ids:
                    raise ValidationError('Container_line_id for product at row no %s is invalid.Please Delete and reload the move line' % str(index+1))
                if self.po_id.id!=line.container_line_id.po_id.id:
                    raise ValidationError('Move Line at row %s Purchase Order is different.Please delete move line and load again' % str(index+1))

    @api.onchange('container_id')
    def onchange_container(self):
        container_id = self.env['container.container'].browse(self.container_id.id) if self.container_id else []
        if container_id:
            po_ids = container_id.container_lines.filtered(lambda rec:rec.state=='customs cleared').mapped('po_id').ids
        else:
            po_ids = []
        self.po_id = False
        return {'domain':{'po_id': [('id', 'in', po_ids)]}}

    @api.onchange('po_id')
    def onchange_po_id(self):
        if self.po_id:
            self.origin = self.po_id.name

    @api.onchange('mbl_id')
    def onchange_mbl_id(self):
        if self.mbl_id:
            self.container_id =False
            self.po_id = False

#    @api.multi
    def unlink_all(self):
        self.move_lines.unlink()

#    @api.multi
#    def write(self,vals):
#        res = super(StockPicking, self).write(vals)
#        self._update_status()
#        return res

    def write(self,vals):
        res = super(StockPicking, self).write(vals)
        for picking in self:
            if picking.state=='done':
                if picking.picking_type_code == 'incoming' \
                 and picking.container_id and picking.picking_type_id.warehouse_id.warehouse_type=='main_warehouse':
                    picking.move_lines.write({'container_ids' : picking.container_id.ids,'mhbl_ids' : picking.move_lines.mapped('container_line_id.mbl_id').ids})
                    container_lines = picking.move_lines.mapped('container_line_id').filtered(lambda rec:rec.state=='customs cleared')
                    if container_lines:
                        warehouse = picking.location_dest_id.display_name
                        container_lines.with_context(post_track_msg=True, warehouse=warehouse).action_received_in_warehouse()
                        picking.po_id.picking_ids._update_status()
                if picking.picking_type_code == 'incoming' \
                 and picking.picking_type_id.warehouse_id.warehouse_type=='ocean':
                    picking._update_status()
        return res

#    @api.multi
    def load_from_container(self):
        move_lines = []
        if self.move_lines:
            self.move_lines.unlink()
        if self.mbl_id and self.container_id and self.po_id:
            container_lines = self.container_id.container_lines.filtered(lambda rec:rec.po_id.id==self.po_id.id and rec.state=='customs cleared')
            for line in container_lines:
                vals=   {'product_id': line.purchase_line.product_id.id,
                       'product_uom_qty' : line.qty_to_load,
                       'product_uom' : 1,
                       'state' :'draft',
                       'origin' : line.purchase_line.order_id.name,
                       'picking_type_id' : self.picking_type_id.id,
                       'location_id' : self.location_id.id,
                       'location_dest_id' :self.location_dest_id.id,
                       'name' : line.purchase_line.product_id.display_name,
                       'container_ids' : [(6, _, self.container_id.ids)],
                       'mhbl_ids' :  [(6, _, container_lines.mapped('mbl_id').ids)],
                       'container_line_id' : line.id
                       }
                move_id = self.env['stock.move'].create(vals)
                move_id.picking_id = self.id

#    def load_from_container(self):
#        move_lines = []
#        if self.move_line_ids_without_package:
#            self.move_line_ids_without_package.unlink()
#        if self.mbl_id and self.container_id and self.po_id:
#            container_lines = self.container_id.container_lines.filtered(lambda rec:rec.po_id.id==self.po_id.id and rec.state=='customs cleared')
#            for line in container_lines:
#                vals = {'product_id': line.purchase_line.product_id.id,
#                        'qty_done' : line.qty_to_load,
#                        'product_uom_id' : 1,
#                        'location_id' : self.location_id.id,
#                        'location_dest_id' :self.location_dest_id.id,
#                        'container_line_id' : line.id
#                       }
#                move_line = self.env['stock.move.line'].create(vals)
#                move_line.picking_id = self.id

#    @api.multi
    def _update_status(self):
        for picking in self:
            order = picking.purchase_id
            warehouse_id = order.picking_type_id.warehouse_id
            # if order and order.picking_type_id and order.picking_type_id.warehouse_id.code == 'OC':
            if order and order.state != 'cancel':
                po_qty_ocean = qty_received = ordered_qty = qty_received_warehouse = 0
                for line in order.order_line:
                    qty_received += line.qty_received
                    ordered_qty += line.product_qty
                    qty_received_warehouse += line.qty_received_warehouse
                    po_qty_ocean += (line.qty_received - line.qty_received_warehouse)
                if warehouse_id.warehouse_type == 'ocean':
                    if po_qty_ocean > 0 :
                        order.state = 'transit'
                    elif qty_received_warehouse == ordered_qty:
                        order.state = 'done'
                    else:
                        order.state = 'purchase'
                else:
                    order.state = (qty_received == ordered_qty) and 'done' or 'purchase'

#    @api.multi
#    def write(self, vals):
#        res = super(StockPicking, self).write(vals)
#        self._update_status()
#        return res

StockPicking()


#class StockWarehouse(models.Model):
#    _inherit = "stock.warehouse"
#    
#    is_delivery_warehouse = fields.Boolean(string="Deliver from this Warehouse")
#    is_receipt_warehouse = fields.Boolean(string="Receive to this Warehouse")
#    
#StockWarehouse()


#class StockRule(models.Model):
#    _inherit = "stock.rule"
#    
#    def _push_prepare_move_copy_values(self, move_to_copy, new_date):
#        #overrides to add the route picking from ocean to main warehouse to the purchase order
#        res = super(StockRule, self)._push_prepare_move_copy_values(move_to_copy, new_date)
#        res.update({'purchase_line_id': move_to_copy.purchase_line_id and move_to_copy.purchase_line_id.id or False})
#        return res
    
#StockRule()
