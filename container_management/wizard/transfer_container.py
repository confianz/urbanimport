## -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SelectContainerWizard(models.TransientModel):
    _name = "select.container.wizard"
    _description = "Transfer Stock To warehouse"

    destination_loc_id = fields.Many2one('stock.location', string="Destination Location", domain=lambda self:self.get_domain())

#    @api.multi
    def get_domain(self):
        oc_loc_id = self.env['stock.warehouse'].search([('warehouse_type', '=', 'ocean')]).lot_stock_id
        domain = [('id', '!=', oc_loc_id.id),('usage','=','internal')]
        return domain

#    @api.multi
#    def transfer_container_to_wh(self):
#        containers = self.env['container.container'].browse(self._context.get('active_ids'))
#        if not all(container.state in ['customs cleared','received partial'] for container in containers):
#            raise UserError("All containers must be in 'Customs Cleared' or 'Received Partaily in WH' state.")
#        container_lines = containers.mapped('container_lines').filtered(lambda rec:rec.state=='customs cleared')
#        if not container_lines:
#            raise UserError("No container Lines found in customs cleared state")
#            
#            
#            
##        location_id = self.env['stock.warehouse'].search([('code', '=', 'OC')]).lot_stock_id
##        picking_ids = container_lines.mapped('po_id').mapped('picking_ids')
##        for line in container_lines:
##            if location_id:
##                move_from_ocean =line.purchase_line.move_ids.filtered(lambda r: r.location_id == location_id.id)
##                if move_from_ocean:
##                    move_from_ocean.write({'quantity_done': line.qty_to_load})
##                    move_from_ocean.picking_id.button_validate()
##                else:
##                    
#            
#            
#            
#            
#        location_id = self.env['stock.warehouse'].search([('code', '=', 'OC')]).lot_stock_id
#        picking_type_id = self.env['stock.picking.type'].search([('code','=','internal'),('warehouse_id.code','=','OC')], limit=1)
#        picking_ids = container_lines.mapped('po_id').mapped('picking_ids')
#        move_lines = {}
#        for line in container_lines:
#            if move_lines.get(line.purchase_line.id):
#                m_line = move_lines.get(line.purchase_line.id)
#                m_line.update({
#                            'product_uom_qty' : m_line.get('product_uom_qty') + line.qty_to_load
#                            })
#                hbl_ids.append(line.hbl_id.id)
#                container_ids.append(line.container_id.id)
#            else:
#                hbl_ids = [line.hbl_id.id]
#                container_ids = [line.container_id.id]
#                move_lines.update({line.purchase_line.id : {'product_id' : line.purchase_line.product_id.id,
#                                   'partner_id' : line.purchase_line.partner_id.id,
#                                   'origin' : line.po_id.name,
#                                   'price_unit' : line.purchase_line.price_unit,
#                                   'name' : line.purchase_line.product_id.name,
#                                   'product_uom_qty' : line.qty_to_load,
#                                   'product_uom' : line.purchase_line.product_uom.id,
#                                   'location_id' : location_id and location_id.id or False,
#                                   'location_dest_id' : self.destination_loc_id.id,
#                                   'product_uom' : line.purchase_line.product_uom.id,
#                                   'picking_type_id' : picking_type_id and picking_type_id.id,
#                                   'quantity_done': line.qty_to_load,
#                                   'hbl_ids' : [(6, _, hbl_ids)],
#                                   'container_ids' :  [(6, _, container_ids)],
##                                   'purchase_line_id': line.purchase_line.id,
#                                    }})
#        for m_line in move_lines.values():
#            new_move = self.env['stock.move'].create(m_line)
#            new_move._action_confirm()
#            new_move._action_assign()
#            new_move._action_done()
#            if new_move.state != 'done':
#                raise UserError(_('Currently mentioned quantities are not available at the location !'))
#            cont_line = m_line.get('line_ids')
#            container_lines.action_received_in_warehouse()
#        containers.create_container_status_note(msg="Received in Warehouse:- %s" %(self.destination_loc_id.display_name), user_id=self.env.user)
##        picking_ids._update_status()
#        return True

    def transfer_container_to_wh(self):
        move_lines = {}
        warehouse = self.destination_loc_id and self.destination_loc_id.display_name.split('/')[0] or 'WH1'
        picking_type_id = self.env['stock.picking.type'].search([('code','=','incoming'),('warehouse_id.code','=',warehouse)], limit=1)
        if self._context.get('direct_transfer', False):
            picking_id = self.env['stock.picking'].browse(self._context.get('active_id'))
            if picking_id.state != 'done':
                raise UserError("Products should available in Ocean inorder to transfer to Warehouse or the picking should be done.")
            for move in picking_id.move_ids_without_package:
                vals = {'product_id' : move.product_id.id,
                       'partner_id' : move.partner_id.id,
                       'origin' : move.origin,
                       'price_unit' : move.price_unit,
                       'procure_method' :'make_to_stock',
                       'name' : move.product_id.name,
                       'purchase_line_id' : False,
                       'product_uom_qty' : move.product_uom_qty,
                       'product_uom' : move.product_uom.id,
                       'location_id' : move.location_dest_id.id,
#                                   'location_dest_id' : dest_input_loc_id and dest_input_loc_id.id or self.destination_loc_id.id,
                       'location_dest_id' : self.destination_loc_id.id,
                       'picking_type_id' : picking_type_id and picking_type_id.id or False,
                       'group_id': move.group_id.id,
                    }
                new_move = self.env['stock.move'].create(vals)
                new_move._action_confirm()
                new_move._action_assign()
                new_move.move_line_ids.write({'qty_done': new_move.product_uom_qty})
                new_move._action_done()
                if new_move.state != 'done':
                    raise UserError(_('Currently mentioned quantities are not available at the location !'))
            picking_id.direct_transfer_done = True
            picking_id.purchase_id.picking_ids._update_status()
            return True
        containers = self.env['container.container'].browse(self._context.get('active_ids'))
        if not all(container.state in ['customs cleared','received partial'] for container in containers):
            raise UserError("All containers must be in 'Customs Cleared' or 'Received Partaily in WH' state.")
        container_lines = containers.mapped('container_lines').filtered(lambda rec:rec.state=='customs cleared')
        if not container_lines:
            raise UserError("No container Lines found in customs cleared state")
        location_id = self.env['stock.warehouse'].search([('warehouse_type', '=', 'ocean')]).lot_stock_id
#        dest_input_loc_id = self.env['stock.warehouse'].search([('warehouse_type', '=', 'main_warehouse')]).wh_input_stock_loc_id
#        picking_type_id = self.env['stock.picking.type'].search([('code','=','internal'),('warehouse_id.warehouse_type','=','main_warehouse')], limit=1)
        
        picking_ids = container_lines.mapped('po_id').mapped('picking_ids')
        
        for line in container_lines:
            if move_lines.get(line.purchase_line.id):
                m_line = move_lines.get(line.purchase_line.id)
                m_line.update({
                            'product_uom_qty' : m_line.get('product_uom_qty') + line.qty_to_load
                            })
                mhbl_ids.append(line.mbl_id.id)
                container_ids.append(line.container_id.id)
            else:
                mhbl_ids = [line.mbl_id.id]
                container_ids = [line.container_id.id]
                move_lines.update({line.purchase_line.id : {'product_id' : line.purchase_line.product_id.id,
                                   'partner_id' : line.purchase_line.partner_id.id,
                                   'origin' : line.po_id.name,
                                   'price_unit' : line.purchase_line.price_unit,
                                   'procure_method' :'make_to_stock',
                                   'name' : line.purchase_line.product_id.name,
                                   'purchase_line_id' : False,
                                   'product_uom_qty' : line.qty_to_load,
                                   'product_uom' : line.purchase_line.product_uom.id,
                                   'location_id' : location_id and location_id.id or False,
#                                   'location_dest_id' : dest_input_loc_id and dest_input_loc_id.id or self.destination_loc_id.id,
                                   'location_dest_id' : self.destination_loc_id.id,
                                   'picking_type_id' : picking_type_id and picking_type_id.id,
                                   'group_id': line.po_id.group_id.id,
                                   'mhbl_ids' : [(6, _, mhbl_ids)],
                                   'container_ids' :  [(6, _, container_ids)]
                                    }})
        
        for m_line in move_lines.values():
            new_move = self.env['stock.move'].create(m_line)
            new_move._action_confirm()
            new_move._action_assign()
            new_move.move_line_ids.write({'qty_done': new_move.product_uom_qty})
            new_move._action_done()
            if new_move.state != 'done':
                raise UserError(_('Currently mentioned quantities are not available at the location !'))
            cont_line = m_line.get('line_ids')
            container_lines.action_received_in_warehouse()
        containers.create_container_status_note(msg="Received in Warehouse:- %s" %(self.destination_loc_id.display_name), user_id=self.env.user)
        picking_ids._update_status()
        return True

SelectContainerWizard()


