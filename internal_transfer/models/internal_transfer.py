# -*- coding: utf-8 -*-

from collections import defaultdict
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare, float_is_zero, float_round

import logging

_logger = logging.getLogger(__name__)


class InternalTransferExtension(models.Model):
    _name = "internal.transfer.extension"
    _description = "Internal Transfer Extension"

    name = fields.Char(
        'Transfer Reference', default=lambda self: _('New'),
        copy=False, required=True,
        states={'done': [('readonly', True)]})

    reference = fields.Char(
        'Reference',
        copy=False,
        states={'done': [('readonly', True)]})

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('done', 'Done'),
    ], string='Status', copy=False, default='draft', readonly=True)

    scheduled_date = fields.Datetime(
        'Scheduled Date', default=lambda self: fields.Datetime.now(),
        states={'done': [('readonly', True)]})

    source_warehouse_id = fields.Many2one(
        'stock.warehouse', "Source Warehouse",
        required=True,
        states={'draft': [('readonly', False)]})

    destination_warehouse_id = fields.Many2one(
        'stock.warehouse', "Destination Warehouse",
        required=True,
        states={'draft': [('readonly', False)]})

    location_id = fields.Many2one(
        'stock.location', "Source Location",
        required=True,
        states={'draft': [('readonly', False)]})

    location_dest_id = fields.Many2one(
        'stock.location', "Destination Location",
        required=True,
        states={'draft': [('readonly', False)]})

    transfer_line_ids = fields.One2many('internal.transfer.line', 'internal_transfer_id', 'Operations', copy=True)
    delivery_picking_id = fields.Many2one('stock.picking', 'Delivery', readonly=True)
    receipt_picking_id = fields.Many2one('stock.picking', 'Receipt', readonly=True)
    carrier_id = fields.Many2one('delivery.carrier', 'Carrier')
    delivery_count = fields.Integer("Deliveries", compute='_compute_deliveries_count')
    receipt_count = fields.Integer("Receipts", compute='_compute_receipt_count')
    date_order = fields.Datetime(string='Date', default=fields.Date.today)

    @api.onchange('source_warehouse_id', 'destination_warehouse_id')
    def _onchange_location_id(self):
        res = {}
        if self.source_warehouse_id :
            res['value'] = {'location_id': self.source_warehouse_id.lot_stock_id.id}
            loc_ids = self.env['stock.location'].search(
                [('id', 'child_of', self.source_warehouse_id.lot_stock_id.id)]).ids
            res['domain'] = {'location_id': [('id', 'in', loc_ids)]}
        if self.destination_warehouse_id:
            res['value'] = {'location_dest_id': self.destination_warehouse_id.lot_stock_id.id}
            loc_ids = self.env['stock.location'].search(
                [('id', 'child_of', self.destination_warehouse_id.lot_stock_id.id)]).ids
            res['domain'] = {'location_dest_id': [('id', 'in', loc_ids)]}
        return res

    def _compute_deliveries_count(self):
        for rec in self:
            rec.delivery_count = self.env['stock.picking'].search_count(
                [('internal_transfer_id', '=', rec.id), ('picking_type_code', '=', 'outgoing')])

    def _compute_receipt_count(self):
        for rec in self:
            rec.receipt_count = self.env['stock.picking'].search_count(
                [('internal_transfer_id', '=', rec.id), ('picking_type_code', '=', 'incoming')])

    def action_view_deliveries(self):
        for rec in self:
            picking_ids = self.env['stock.picking'].search(
                [('internal_transfer_id', '=', self.id), ('picking_type_code', '=', 'outgoing')]).mapped('id')
            list_view_id = self.env.ref('stock.vpicktree').id
            form_view_id = self.env.ref('stock.view_picking_form').id
            action = {
                'name': 'Deliveries',
                'type': 'ir.actions.act_window',
                'views': [(list_view_id, 'tree'), (form_view_id, 'form')],
                'view_mode': 'tree,form',
                'domain': [('id', 'in', picking_ids)],
                'res_model': 'stock.picking',
            }
        return action

    def action_view_receipts(self):
        for rec in self:
            picking_ids = self.env['stock.picking'].search(
                [('internal_transfer_id', '=', self.id), ('picking_type_code', '=', 'incoming')]).mapped('id')
            list_view_id = self.env.ref('stock.vpicktree').id
            form_view_id = self.env.ref('stock.view_picking_form').id
            action = {
                'name': 'Receipts',
                'type': 'ir.actions.act_window',
                'views': [(list_view_id, 'tree'), (form_view_id, 'form')],
                'view_mode': 'tree,form',
                'domain': [('id', 'in', picking_ids)],
                'res_model': 'stock.picking',
            }
        return action

    def action_transfer(self):
        for rec in self:
            source_location = rec.location_id
            dst_location = rec.location_dest_id
            reference = rec.name
            carrier_id = rec.carrier_id
            source_warehouse = self.env['stock.warehouse'].search([('code', '=', source_location.display_name.split('/')[0])])
            dest_warehouse = self.env['stock.warehouse'].search([('code', '=', dst_location.display_name.split('/')[0])])
            picking_type_out = self.env['stock.picking.type'].search(
                [('code', '=', 'outgoing'), ('warehouse_id', '=', source_warehouse.id)], limit=1)
            picking_type_in = self.env['stock.picking.type'].search(
                [('code', '=', 'incoming'), ('warehouse_id', '=', dest_warehouse.id)], limit=1)
            internal_transit_loc = self.env['stock.location'].search(
                [('usage', '=', 'internal_transit')], limit=1)
            if not internal_transit_loc:
                raise UserError(_('Please configure an Internal Transit Location'))
            if not picking_type_in.warehouse_id.partner_id:
                raise UserError(_('Please enter the address for the destination warehouse'))
            incoming_move_vals = {}
            outgoing_move_vals = {}
            incoming_picking = self.env['stock.picking'].create({
                'location_id': internal_transit_loc.id,
                'location_dest_id': dst_location.id,
                'partner_id': picking_type_out.warehouse_id.partner_id.id,
                'origin': reference,
                'picking_type_id': picking_type_in.id,
                'internal_transfer_id': rec.id,
#                'move_lines': incoming_move_vals,
            })
            outgoing_picking = self.env['stock.picking'].create({
                'location_id': source_location.id,
                'location_dest_id': internal_transit_loc.id,
                'partner_id': picking_type_in.warehouse_id.partner_id.id,
                'carrier_id': carrier_id.id,
                'origin': reference,
                'picking_type_id': picking_type_out.id,
                'internal_transfer_id': rec.id,
#                'move_lines': outgoing_move_vals,
            })
            for line in rec.transfer_line_ids:
                product = line.product_id
                incoming_move_vals = {
                    'name': product.name,
                    'product_id': product.id,
                    'product_uom': product.uom_id.id,
                    'picking_type_id': picking_type_in.id,
                    'product_uom_qty': line.ordered_qty,
                    'location_id': internal_transit_loc.id,
                    'location_dest_id': dst_location.id,
                    'warehouse_id': picking_type_in.warehouse_id.id,
                    'procure_method': 'make_to_stock',
                    'picking_id': incoming_picking.id,
                }
                incoming_move = self.env['stock.move'].create(incoming_move_vals)
                outgoing_move_vals = {
                    'name': product.name,
                    'product_id': product.id,
                    'product_uom': product.uom_id.id,
                    'product_uom_qty': line.ordered_qty,
                    'picking_type_id': picking_type_out.id,
                    'location_id': source_location.id,
                    'location_dest_id': internal_transit_loc.id,
                    'warehouse_id': picking_type_out.warehouse_id.id,
                    'procure_method': 'make_to_stock',
                    'picking_id': outgoing_picking.id,
                }
                outgoing_move = self.env['stock.move'].create(outgoing_move_vals)
                outgoing_move.move_dest_ids = [(4, incoming_move.id)]
                # line.is_process=TRue
            incoming_picking.action_assign()
            outgoing_picking.action_assign()
        self.write(
            {'delivery_picking_id': outgoing_picking.id, 'receipt_picking_id': incoming_picking.id, 'state': 'confirm'})
        return True

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('internal.transfer.extension')
        res = super(InternalTransferExtension, self).create(vals)
        return res

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("You can only delete a Draft transfer.")
            return super(InternalTransferExtension, rec).unlink()

InternalTransferExtension()


class InternalTransferLine(models.Model):
    _name = "internal.transfer.line"
    _description = "Internal Transfer Line"

    name = fields.Char('Description')

    product_id = fields.Many2one(
        'product.product', 'Product',
        domain=[('type', 'in', ['product', 'consu'])], required=True)
    ordered_qty = fields.Float('Ordered Quantity', digits='Ordered Quantity', default=0.0)
    product_tmpl_id = fields.Many2one(
        'product.template', 'Model',
        related='product_id.product_tmpl_id', store=True)
    internal_transfer_id = fields.Many2one('internal.transfer.extension', 'Internal Transfer Reference')

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.description_sale


InternalTransferLine()


class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    @api.model
    def run(self, procurements, raise_user_error=True):
    
        def raise_exception(procurement_errors):
            if raise_user_error:
                dummy, errors = zip(*procurement_errors)
                raise UserError('\n'.join(errors))
            else:
                raise ProcurementException(procurement_errors)

        actions_to_run = defaultdict(list)
        procurement_errors = []
        
        

        m_warehouse = self.env['stock.warehouse'].search([('warehouse_type', '=', 'main_warehouse')], limit=1)
        oc_warehouse = self.env['stock.warehouse'].search([('warehouse_type', '=', 'ocean')], limit=1)
        s_warehouse = self.env['stock.warehouse'].search([('warehouse_type', '=', 'sub_warehouse')], limit=1)
        internal_transit_loc = self.env['stock.location'].search(
            [('usage', '=', 'internal_transit')], limit=1)
        main_warehouse_loc = m_warehouse and m_warehouse.lot_stock_id
        ocean_loc = oc_warehouse and oc_warehouse.lot_stock_id
        s_warehouse_loc = s_warehouse and s_warehouse.lot_stock_id
        main_warehouse_loc_ids = self.env['stock.location'].search(
            [('id', 'child_of', main_warehouse_loc.id)]).ids
        s_warehouse_loc_ids = self.env['stock.location'].search(
            [('id', 'child_of', s_warehouse_loc.id)]).ids
        ocean_loc_ids = self.env['stock.location'].search(
            [('id', 'child_of', ocean_loc.id)]).ids
        total_quantity = 0.0

        procurement_errors = []
        for procurement in procurements:
            procurement.values.setdefault('company_id', procurement.location_id.company_id)
            procurement.values.setdefault('priority', '0')
            procurement.values.setdefault('date_planned', fields.Datetime.now())
            if (
                procurement.product_id.type not in ('consu', 'product') or
                float_is_zero(procurement.product_qty, precision_rounding=procurement.product_uom.rounding)
            ):
                continue
            rule = self._get_rule(procurement.product_id, procurement.location_id, procurement.values)
            if not rule:
                error = _('No rule has been found to replenish "%s" in "%s".\nVerify the routes configuration on the product.') %\
                    (procurement.product_id.display_name, procurement.location_id.display_name)
                procurement_errors.append((procurement, error))
            else:
                action = 'pull' if rule.action == 'pull_push' else rule.action
                actions_to_run[action].append((procurement, rule))

        if procurement_errors:
            raise_exception(procurement_errors)
        for action, procurements in actions_to_run.items():
            proc_list = []
            balance_qty = procurements[0][0].product_qty
            for procurement in procurements:
                loc = procurement[0].values.get('orderpoint_id')
                stock_quant = self.env['stock.quant'].read_group(
                    [('product_id', '=', procurement[0].product_id.id)],
                    ["id", "quantity"],
                    groupby=['location_id'],
                    orderby='',
                    lazy=False)

                quant = oc_quant = sub_quant = 0.0

                for line in stock_quant:
                    if line.get('location_id', False):
                        if line.get('location_id')[0] in main_warehouse_loc_ids:
                            quant += line.get('quantity', 0)
                        if line.get('location_id')[0] in ocean_loc_ids:
                            oc_quant += line.get('quantity', 0)
                        if line.get('location_id')[0] in s_warehouse_loc_ids:
                            sub_quant += line.get('quantity', 0)
                if loc:
                    # if order_point exists then only this loop will excecute.

                    if loc.warehouse_id and loc.warehouse_id.warehouse_type == 'sub_warehouse':
                        intern_tranf = self.env['internal.transfer.extension'].search(
                            [('location_dest_id', '=', loc.location_id.id),
                             ('location_id', '=', main_warehouse_loc.id),
                             ('state', '=', 'draft')])
                        if quant and quant != 0 and loc:
                            if balance_qty < quant:
                                if intern_tranf:
                                    if procurement[0].product_id.id in intern_tranf.transfer_line_ids.mapped('product_id').ids:
                                        product_line = intern_tranf.transfer_line_ids.filtered(lambda r: r.product_id == procurement[0].product_id)
                                        if product_line.ordered_qty < balance_qty:
                                            product_line.write({'ordered_qty': balance_qty})
                                    else:
                                        intern_tranf.write({'transfer_line_ids': [(0, 0, {
                                            'name': procurement[0].product_id.name,
                                            'ordered_qty': balance_qty,
                                            'product_id': procurement[0].product_id.id})]})

                                    balance_qty -= balance_qty
                                else:
                                    record = self.create_intern_traf_record(loc.location_id, main_warehouse_loc,
                                                                            procurement[0].product_id.name, balance_qty,
                                                                            procurement[0].product_id)

#                                    record.action_transfer()
                                    balance_qty -= balance_qty
                            else:
                                if intern_tranf:
                                    if procurement[0].product_id in intern_tranf.transfer_line_ids.mapped('product_id'):
                                        product_line = intern_tranf.transfer_line_ids.filtered(lambda r: r.product_id == procurement[0].product_id)
                                        if product_line.ordered_qty < quant:
                                            product_line.write({'ordered_qty': quant})
                                    else:
                                        intern_tranf.write({'transfer_line_ids': [(0, 0, {
                                            'name': procurement[0].product_id.name,
                                            'ordered_qty': quant,
                                            'product_id': procurement[0].product_id.id})]})

                                    balance_qty -= quant
                                else:
                                    record = self.create_intern_traf_record(loc.location_id, main_warehouse_loc,
                                                                            procurement[0].product_id.name, quant,
                                                                            procurement[0].product_id)
#                                    record.action_transfer()
                                    balance_qty -= quant

                        if balance_qty > 0:
                            rec = self.env['internal.transfer.exception'].sudo().create({
                                'order_point_id': loc.id,
                                'product_id': procurement[0].product_id.id,
                                'message': _(
                                    'while processing the re-ordering rule for "%s", %s quantity is unavailable in "%s" warehouse') % (
                                               procurement[0].product_id.name, balance_qty, m_warehouse.name),
                                'quantity': balance_qty,
                                'warning_date': fields.Datetime.now()
                            })
                            return True
                    if loc.warehouse_id and loc.warehouse_id.warehouse_type == 'main_warehouse':
                        if balance_qty > 0:
                            total_quantity = quant + oc_quant + sub_quant
                            other_wh_qty = oc_quant + sub_quant
                            balance_qty -= other_wh_qty
                            if float_compare(total_quantity, loc.product_min_qty, precision_rounding=loc.product_uom.rounding) <= 0:
                                proc_list.append((procurement[0]._replace(product_qty = balance_qty), procurement[-1]))
                            else:
                                return True
            if balance_qty > 0:
                if hasattr(self.env['stock.rule'], '_run_%s' % action):
                    try:
                        getattr(self.env['stock.rule'], '_run_%s' % action)(proc_list or procurements)
                    except UserError as e:
                        errors.append(e.name)
                else:
                    _logger.error("The method _run_%s doesn't exist on the procurement rules" % action)
            if procurement_errors:
                raise_exception(procurement_errors)
        return True

    def create_intern_traf_record(self, loc_dest_id, w_loc, description, qty, product):
        source_warehouse = self.env['stock.warehouse'].search([('code', '=', w_loc.display_name.split('/')[0])])
        dest_warehouse = self.env['stock.warehouse'].search([('code', '=', loc_dest_id.display_name.split('/')[0])])
        record = self.env['internal.transfer.extension'].create({
            'source_warehouse_id': source_warehouse and source_warehouse.id,
            'destination_warehouse_id': dest_warehouse and dest_warehouse.id,
            'location_dest_id': loc_dest_id.id,
            'location_id': w_loc.id,
            'transfer_line_ids': [(0, 0, {'name': description,
                                          'ordered_qty': qty,
                                          'product_id': product.id})]
        })
        return record


ProcurementGroup()
