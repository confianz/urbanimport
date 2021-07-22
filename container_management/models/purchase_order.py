# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models,api,_


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    containers_count = fields.Integer(string="# Containers", compute = 'compute_container_lines')
    freight_bills_count = fields.Integer(string="Freight Bills Count", compute='compute_freight_bills_count')
    container_line_ids = fields.One2many('container.line', 'po_id', string="Container Lines")
    is_ocean_order = fields.Boolean(string="Is Ocean Order", compute='compute_is_ocean_order', store=True, default=False)
    state = fields.Selection([
        ('draft', 'RFQ'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('transit','In-Transit'),
        ('done', 'Received'),
        ('cancel', 'Cancelled')
        ], string='Status', readonly=True, index=True, copy=False, default='draft', tracking=True)
    warehouse_type = fields.Selection(related="picking_type_id.warehouse_id.warehouse_type", string="Warehouse Type")
    end_loc_id = fields.Many2one('stock.location', string='Final Transfer to', domain=lambda self:self.get_domain())
    expected_final_transfer = fields.Datetime(string="Expected Final Transfer")

    def get_domain(self):
        oc_loc_id = self.env['stock.warehouse'].search([('warehouse_type', '=', 'ocean')]).lot_stock_id
        domain = [('id', 'not in', oc_loc_id.ids),('usage','=','internal')]
        return domain

    @api.depends('state','order_line.is_ocean_line')
    def compute_is_ocean_order(self):
        for order in self:
            order.is_ocean_order = all(line.is_ocean_line  for line in order.order_line)

#    @api.multi
    def compute_container_lines(self):
        """
        Compute the No. of containers associated with the purchase order.
        """
        for order in self:
            order.containers_count = len(order.container_line_ids.mapped('container_id'))

    @api.depends('order_line.move_ids.returned_move_ids',
                 'order_line.move_ids.state',
                 'order_line.move_ids.picking_id')
    def _compute_picking(self):
        for order in self:
            pickings = self.env['stock.picking']
            for line in order.order_line:
                # We keep a limited scope on purpose. Ideally, we should also use move_orig_ids and
                # do some recursive search, but that could be prohibitive if not done correctly.
                moves = line.move_ids | line.move_ids.mapped('returned_move_ids')
                pickings |= moves.mapped('picking_id')
            po_pickings = self.env['stock.picking'].search([('origin', '=', order.name)])
            for pick in po_pickings:
                if pick not in pickings:
                    pickings |= pick
            order.picking_ids = pickings
            order.picking_count = len(pickings)

#    def action_view_picking(self):
#        """ This function returns an action that display existing picking orders of given purchase order ids. When only one found, show the picking immediately.
#        """
#        action = self.env.ref('stock.action_picking_tree_all')
#        result = action.read()[0]
#        location_id = self.env['stock.warehouse'].search([('code', '=', 'OC')]).lot_stock_id
#        # override the context to get rid of the default filtering on operation type
#        result['context'] = {'default_partner_id': self.partner_id.id, 'default_origin': self.name, 'default_picking_type_id': self.picking_type_id.id}
##        pick_ids = self.mapped('picking_ids')
#        #override the pick_ids to get two step picking related to PO
#        pick_ids = self.env['stock.picking'].search([('origin', '=', self.name), ('location_id', '!=', location_id.id)])
#        # choose the view_mode accordingly
#        if not pick_ids or len(pick_ids) > 1:
#            result['domain'] = "[('id','in',%s)]" % (pick_ids.ids)
#        elif len(pick_ids) == 1:
#            res = self.env.ref('stock.view_picking_form', False)
#            form_view = [(res and res.id or False, 'form')]
#            if 'views' in result:
#                result['views'] = form_view + [(state,view) for state,view in result['views'] if view != 'form']
#            else:
#                result['views'] = form_view
#            result['res_id'] = pick_ids.id
#        return result

#    @api.depends('order_line.move_ids.returned_move_ids',
#                 'order_line.move_ids.state',
#                 'order_line.move_ids.picking_id')
#    def _compute_picking(self):
#        for order in self:
#            pickings = self.env['stock.picking']
#            for line in order.order_line:
#                # We keep a limited scope on purpose. Ideally, we should also use move_orig_ids and
#                # do some recursive search, but that could be prohibitive if not done correctly.
#                moves = line.move_ids | line.move_ids.mapped('returned_move_ids')
#                pickings |= moves.mapped('picking_id')
#            order.picking_ids = pickings
#            all_pickings = pickings.search([('origin', '=', self.name)])
#            order.picking_count = len(all_pickings)

PurchaseOrder()


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    qty_loaded_in_cont = fields.Float(string="Qty Loaded In Cont.", compute='compute_qty_loaded_in_container')
    is_ocean_line = fields.Boolean(string="Is Ocean Line", compute='compute_is_ocean_line', store=True, default=False)
    container_line_ids = fields.One2many('container.line','purchase_line',string="Container Lines")
#    move_line_ids = fields.One2many('stock.move','purchase_line_id',string="Move_lines")
    qty_received_warehouse = fields.Float(compute="_compute_qty_received_warehouse", string="Received Qty(Warehouse)")
    qty_received_ocean = fields.Float(compute="_compute_qty_received_ocean", string="Received Qty(Ocean)")
    qty_to_ship = fields.Float(compute="_compute_qty_to_ship", string="Qty to Ship")

    @api.depends('order_id')
    def _compute_qty_received_warehouse(self):
        for line in self:
            if line.order_id.picking_type_id.warehouse_id.warehouse_type == 'ocean':
                domain = [('origin', '=', line.order_id.name), ('product_id', '=', line.product_id.id)]
                location_id = self.env['stock.warehouse'].search([('warehouse_type', '=', 'ocean')]).lot_stock_id
    #            ('warehouse_type', '=', 'ocean'), 
                int_moves = self.env['stock.move'].search([('picking_type_id.code','=','incoming'),('picking_id.origin','=',line.order_id.name),('product_id', '=', line.product_id.id), ('location_id', 'in', location_id.ids), ('state', '=', 'done')]).filtered(lambda r : r.location_dest_id.location_id != location_id)
    #            for picking in line.order_id.picking_ids:
    #                qty_received_warehouse = 0
    #                moves = picking.move_lines.search(domain).filtered(
    #                    lambda r : r.picking_type_id.code == 'internal' and r.location_dest_id.location_id != location_id)
                qty_received_warehouse = 0.0
                for move in int_moves:
                    qty_received_warehouse += move.product_uom_qty
                line.qty_received_warehouse = qty_received_warehouse
            else:
                line.qty_received_warehouse = line.qty_received
            
    @api.depends('order_id', 'qty_received_warehouse', 'qty_received', 'product_qty')
    def _compute_qty_to_ship(self):
        for line in self:
            line.qty_to_ship = line.product_qty - line.qty_received_ocean - line.qty_received_warehouse
        
    @api.depends('order_id', 'qty_received_warehouse', 'qty_received')
    def _compute_qty_received_ocean(self):
        for line in self:
            if line.order_id.picking_type_id.warehouse_id.warehouse_type == 'ocean':
                line.qty_received_ocean = line.qty_received - line.qty_received_warehouse
            else:
                line.qty_received_ocean = 0.0
#            domain = [('origin', '=', line.order_id.name), ('product_id', '=', line.product_id.id)]
#            location_id = self.env['stock.warehouse'].search([('warehouse_type', '=', 'ocean'), ('code', '=', 'OC')]).lot_stock_id
#            int_moves = self.env['stock.move'].search([('picking_type_id.code','=','incoming'),('picking_id.origin','=',line.order_id.name),('product_id', '=', line.product_id.id)]).filtered(lambda r : r.location_dest_id.location_id == location_id)

##            for picking in line.order_id.picking_ids:
##                qty_received_warehouse = 0
##                moves = picking.move_lines.search(domain).filtered(
##                    lambda r : r.picking_type_id.code == 'internal' and r.location_dest_id.location_id != location_id)

#            qty_received_ocean = 0.0
#            for move in int_moves:
#                qty_received_ocean += move.product_uom_qty
#                line.qty_received_ocean = qty_received_ocean

    @api.depends('order_id.state', 'move_ids.state')
    def _compute_qty_received(self):
        for line in self:
            if line.order_id.state not in ['purchase', 'done', 'transit']:
                line.qty_received = 0.0
                continue
            if line.product_id.type not in ['consu', 'product']:
                line.qty_received = line.product_qty
                continue
            total = 0.0
            for move in line.move_ids:
                if move.state == 'done':
                    if move.product_uom != line.product_uom:
                        total += move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom)
                    else:
                        total += move.product_uom_qty
            line.qty_received = total

        # purchase_mrp
#        for line in self.filtered(lambda x: x.move_ids and x.product_id.id not in x.move_ids.mapped('product_id').ids):
#            bom = self.env['mrp.bom']._bom_find(product=line.product_id, company_id=line.company_id.id)
#            if bom and bom.type == 'phantom':
#                line.qty_received = line._get_bom_delivered(bom=bom)

#    @api.multi
    def unlink(self):
        for line in self:
            if line.order_id.state in ['purchase', 'done','transit']:
                raise UserError(_('Cannot delete a purchase order line which is in state \'%s\'.') %(line.state,))
        return super(PurchaseOrderLine, self).unlink()


    @api.depends('state','qty_received')
    def compute_is_ocean_line(self):
        for line in self:
            if line.qty_received >= line.product_qty:
                line.is_ocean_line = True
            else:
                line.is_ocean_line = False

#    @api.multi
    def compute_qty_loaded_in_container(self):
        for line in self:
            container_lines = line.container_line_ids.filtered(lambda rec:rec.purchase_line.id == line.id and rec.state in ['draft','ready'])
            line.qty_loaded_in_cont = sum(container_lines.mapped('qty_to_load'))

#    @api.multi
    def view_container_lines(self):
        action = self.env.ref('container_management.action_view_container_lines_2')
        result = action.read()[0]
        result['context'] = {'search_default_purchase_line': self.id,
                            'default_purchase_line': self.id
                            }
        return result


PurchaseOrderLine()
