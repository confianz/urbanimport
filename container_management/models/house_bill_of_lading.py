# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models,api,_
from odoo.exceptions import ValidationError,UserError
from datetime import datetime
from math import floor
import itertools
import json
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

def truncate(f, n):
    return floor(f * 10 ** n) / 10 ** n


class MasterHouseBillLading(models.Model):
    _name = 'master.house.bill.lading'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Master house bill lading"


    READONLY_STATES = {'in ocean': [('readonly', True)],
                      'received port': [('readonly', True)],
                      'customs cleared': [('readonly', True)],
                      'received partial' :  [('readonly', True)],
                      'received warehouse' :  [('readonly', True)],
                      }


    name = fields.Char(string="Name", compute="_compute_name", store=False)
    mbl_no = fields.Char(string="MBL No.", copy=False)
    mbl_no_copy = fields.Char(string="MBL No.(copy)", related="mbl_no")
    vessel_name = fields.Char(string="Vessel Name")
    etd = fields.Date(string="Ship Date")
    freight_forwarder = fields.Many2one('res.partner', string="Freight Forwarder", states={'received port': [('readonly', True)]})
    customs_agent_id = fields.Many2one('res.partner', string="Customs Agents", states={'received port': [('readonly', True)]} )
#    hbl_ids = fields.One2many('house.bill.lading','mhbl_id', string="House Bill Lading",ondelete='cascade', states=READONLY_STATES)
    hbl_line_ids = fields.One2many('container.line', 'mbl_id', string="Containers", ondelete="cascade", states=READONLY_STATES)
#    hbl_count = fields.Integer(string="HBL Count", compute="compute_hbl_count")
    state = fields.Selection([('draft','Draft'),
                              ('ready','Ready To Ship'),
                              ('in ocean', 'In Ocean'),
                              ('received port', 'Received In Port'),
                              ('customs cleared', 'Customs Cleared')], index=True, copy=False, store=True, track_visibility='always',default="draft", string="State")
    
#    state = fields.Selection([('draft', 'Draft'),
#                              ('ready','Ready To Ship'),
#                              ('in ocean', 'In Ocean'),
#                              ('received port', 'Received In Port'),
#                              ('customs cleared','Customs Cleared'),
#                              ('received partial', 'Partaily Received in Warehouse'),
#                              ('received warehouse', 'Received In Warehouse')], compute='compute_state',  index=True, copy=False, store=True, track_visibility='always', string="State")
                              
    container_ids = fields.One2many('container.container', 'mhbl_id', string="Containers", ondelete="cascade")
    container_count = fields.Integer(string="Containers", compute='compute_container_count')
    stock_move_count = fields.Integer(string="Stock Moves", compute='compute_stock_move_count', default=0)
    merch_process_fee = fields.Float(string="Merchendise Processing Fee", compute='compute_customs_fee')
    harbour_maint_fee = fields.Float(string="Harbour Maintenance Fee", compute='compute_customs_fee')
    total_duty = fields.Float(string="Total Duty", compute='compute_customs_fee')
    customs_line_total = fields.Monetary(string="Customs Duty", compute='compute_customs_line_total', store=True)
    bill_count = fields.Integer(string="Bills Count", compute='compute_hbl_bills')
    bill_ids = fields.Many2many('account.move', string="Bills", compute='compute_hbl_bills')
    port_date = fields.Date(string="Estimated At Port Date")
    date_at_ocean = fields.Date(string="Ocean Received Date")
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self:self.env.user.company_id.currency_id)
    
    @api.model
    def create(self, vals):
        
        res = super(MasterHouseBillLading, self).create(vals)
        return res

#    @api.multi
    def compute_hbl_bills(self):
        for hbl in self:
            bills = self.env['account.move'].search([('mhbl_id', '=', self.id)])
            hbl.bill_ids = bills
            hbl.bill_count = len(bills)

#    @api.multi
    def compute_customs_fee(self):
        customs_partner_id = self.env['res.partner'].search([('us_customs','=',True)], limit=1)
        merch_p_fee = customs_partner_id.merch_process_fee
        harbour_m_fee = customs_partner_id.harbour_maint_fee
        for rec in self:
            c_line_ids = rec.hbl_line_ids.mapped('line_customs_id')
            m_fee = 0.0
            h_fee = 0.0

            if merch_p_fee and  harbour_m_fee:
                hts_code_list = c_line_ids.mapped(lambda line : list(line.hts_ids.mapped('code')))
                hts_code_group_by = itertools.groupby(sorted(hts_code_list))
                for code_list, group in hts_code_group_by:
                    purchase_total = sum(c_line_ids.filtered(lambda line:line.hts_ids.mapped('code') == code_list).mapped(lambda line:line.quantity * line.unit_price))
                    purchase_total = round(purchase_total)
                    m_fee += rec.currency_id.round((purchase_total*merch_p_fee)/100)
                    h_fee += rec.currency_id.round((purchase_total * harbour_m_fee)/100)
                rec.merch_process_fee = m_fee
                rec.harbour_maint_fee = h_fee
            rec.total_duty = (rec.merch_process_fee + rec.harbour_maint_fee + rec.customs_line_total) or 0.0

    @api.depends('hbl_line_ids.line_customs_id')
    def compute_customs_line_total(self):
        for rec in self:
            c_lines = rec.hbl_line_ids.mapped('line_customs_id')
            customs_total = 0.0
            hts_code_list = c_lines.mapped(lambda line : list(line.hts_ids.mapped('code')))
            hts_code_group_by = itertools.groupby(sorted(hts_code_list))
            for code_list, group in hts_code_group_by:
                hts_code_ids = c_lines.filtered(lambda line:line.hts_ids.mapped('code') == code_list).mapped('hts_ids')
                purchase_total = sum(c_lines.filtered(lambda line:line.hts_ids.mapped('code') == code_list).mapped('price_total'))
                for hts_id in hts_code_ids:
                    purchase_total = round(purchase_total)
                    total = rec.currency_id.round((purchase_total * hts_id.percentage) / 100)
                    extra_duty = 0.0
                    if hts_id.extra_duty_applicable:
                        qty = sum(c_lines.filtered(lambda line:line.hts_ids.mapped('code') == code_list).mapped('quantity'))
                        extra_duty = (truncate((qty / hts_id.quantity),1) * hts_id.extra_duty)
                    customs_total += (total + rec.currency_id.round(extra_duty))
            rec.customs_line_total = customs_total
            return True

    @api.depends('mbl_no')
    def _compute_name(self):
        for record in self:
            record.name = record.mbl_no  if record.mbl_no else ""

#    @api.multi
#    def compute_hbl_count(self):
#        for rec in self:
#            rec.hbl_count = len(rec.hbl_ids)

#    @api.multi
    def action_ready(self):
        self.ensure_one()
        purchase_lines = self.hbl_line_ids.mapped('purchase_line')
        qty_to_load = self.hbl_line_ids.mapped('qty_to_load')
        if qty_to_load and not all(qty_to_load):
            raise ValidationError("Qty to Load cannot be empty, it should be a non zero valid number.")
        for line in purchase_lines:
            qty_to_transfer = line.qty_received + sum(self.hbl_line_ids.filtered(lambda p_line : p_line.purchase_line.id == line.id).mapped('qty_to_load'))
            if line.product_qty < qty_to_transfer :
                raise ValidationError("""The total number of quantities loaded in different containers for purchase line '%s' is %s.This exceeded purchase line's ordered quantity(%s).""" % (line.name, qty_to_transfer, line.product_qty))
        self.hbl_line_ids.write({'state' : 'ready'})
        
        if not self._context.get('action_ready_from_container', False):
            self.write({'state' : 'ready'})
            self.mapped('container_ids').create_container_status_note(msg="Ready To Ship", user_id=self.env.user)

    def calculate_quantity_to_receive(self):
        """
        Calculate the quantity that we want to receive while
        validating the Delivery order.
        """
        po_lines = []
        hbl_lines = self.hbl_line_ids.sorted(key=lambda line:line.purchase_line.id)
        for line in hbl_lines:
            if po_lines and po_lines[-1].get('p_line').id == line.purchase_line.id:
                dict_line = po_lines[-1]
                dict_line.update({'qty' : dict_line['qty'] + line.qty_to_load})
            else:
                po_lines.append({'p_line' : line.purchase_line,
                                 'qty' : line.qty_to_load,
                                 'po_id' : line.po_id,
                                 'product_id' : line.purchase_line.product_id.id,
                                 'hbl_id' : line.mbl_id
                                 })

        return po_lines

#    @api.multi
    def validate_to_ocean(self):
        self.ensure_one()
#        self.hbl_ids.validate_to_ocean()
        self.with_context(action_ready_from_container=True).action_ready()
        hbl_ids = self
        po_lines = self.calculate_quantity_to_receive()
        picking = []
#        oc_loc_id = self.env['stock.warehouse'].search([('code', '=', 'OC')]).lot_stock_id
        for line in po_lines:
            p_order = line.get('po_id')
            picking_id = p_order.picking_ids.filtered(lambda rec:rec.state not in ['draft','cancel','done'] and rec.warehouse_type == 'ocean')
            if not picking_id:
                raise ValidationError("Shipment for purchase order %s either in 'Draft','Cancel' or 'Done' status.This can't be moved to ocean" % (p_order.name))
            if len(picking_id) == 1:
                picking_move_id = picking_id.mapped('move_ids_without_package').filtered(lambda rec:rec.product_id.id == line.get('product_id'))
                if picking_move_id.product_qty < line.get('qty'):
                    raise ValidationError("""Shipped  Qty for the product '%s(%s)' is exceeded Ordered Qty.Please check Qty loaded in the Container(s).""" % (line.get('p_line').name,line.get('p_line').order_id.name))
                picking_move_id.write({'quantity_done' : line.get('qty')})
                picking.append(picking_id)
        picking = set(picking)
        for picking_id in picking:
            result=picking_id.button_validate()
            picking_id.write({'carrier' : ("BOL # %s")%(line.get('hbl_id',False) and line.get('hbl_id',False).mbl_no),
                              'bill_of_lading' : line.get('hbl_id',False) and line.get('hbl_id',False).name
                               })
 
            if type(result) != bool and result.get('res_id', False):
                res_id = self.env['stock.backorder.confirmation'].browse(result['res_id'])
                res_id.process()
            purchase_id = picking_id.purchase_id
#            invoice_id = picking_id.invoice_id
#            if invoice_id and invoice_id.state == 'draft' :
#                invoice_id.write({
#                    'reference': '%s / %s' % (line.get('hbl_id').mbl_no, purchase_id.name),
#                    'date_invoice': line.get('hbl_id').mhbl_id.etd,
#                })
#                invoice_id.action_invoice_open()

            if picking_id.move_lines  and picking_id.warehouse_type == 'ocean' and line.get('hbl_id').etd:
#                move_date = line.get('hbl_id').mhbl_id.etd.strftime("%Y-%m-%d") + " 12:00:00"
                move_date = str(line.get('hbl_id').etd) + " 12:00:00"
                picking_id.move_lines.write({'date' : datetime.strptime(move_date, DEFAULT_SERVER_DATETIME_FORMAT)})

        self.action_move_to_ocean()
        self.hbl_line_ids.get_duty_percentage()
#        return True

        
        if not self._context.get('validate_to_ocean_from_container', False):
            self.write({'state' : 'in ocean','date_at_ocean' : datetime.today()})
            self.mapped('container_ids').create_container_status_note(msg="Received In Ocean", user_id=self.env.user)

    def action_move_to_ocean(self):
        self.hbl_line_ids.write({'state' : 'in ocean'})

#    @api.multi
    def action_receive_in_port(self):
        self.ensure_one()
        self.hbl_line_ids.write({'state' : 'received port'})
        if not self._context.get('action_receive_in_port_from_container', False):
            self.write({'state': 'received port'})
            self.mapped('container_ids').create_container_status_note(msg="Received In Port", user_id=self.env.user)


#    @api.multi
    def compute_container_count(self):
        for rec in self:
            rec.container_count = len(rec.container_ids)

#    @api.multi
    def action_view_containers(self):
        """
        Return containers associated with the MBL.
        """
        self.ensure_one()
        action = self.env.ref('container_management.action_view_container')
        result = action.read()[0]
        container_ids =  self.hbl_line_ids.mapped('container_id').ids
        if len(container_ids) > 0:
            result['domain'] = "[('id', 'in', " + str(container_ids) + ")]"
        return result

#    @api.multi
    def compute_stock_move_count(self):
        for hbl in self:
            stock_moves = self.env['stock.move'].search([('mhbl_ids','in',self.ids)])
            hbl.stock_move_count = len(stock_moves)

#    @api.multi
    def action_view_stock_moves(self):
        """
        Return stock moves action to view the stock moves
        associated with the MHBL.
        """
        self.ensure_one()
        action = self.env.ref('stock.stock_move_action')
        result = action.read()[0]
#        hbl_ids =  self.hbl_ids.ids
#        if len(hbl_ids) > 0:
        result['domain'] = "[('mhbl_ids', 'in', " + str(self.ids) + ")]"
        return result

#    @api.multi
    def action_view_vendor_bills(self):
        self.ensure_one()
        action = self.env.ref('container_management.action_bills_tree_view')
        result = action.read()[0]

        #override the context to get rid of the default filtering
        result['context'] = {'default_type' : 'in_invoice','default_mhbl_id': self.id,'cont_bills': True}

        if len(self.bill_ids) != 1:
            result['domain'] = "[('id', 'in', " + str(self.bill_ids.ids) + ")]"
        elif len(self.bill_ids) <= 1:
            res = self.env.ref('container_management.freight_forwarder_vendor_bill', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = self.bill_ids.id
        return result

#    @api.multi
    def clear_all_hbl_customs(self):
        for record in self:
            hbl_ids = record.hbl_ids.filtered(lambda hbl:hbl.state=='received port')
            if hbl_ids:
                hbl_ids.action_clear_customs()

    def action_clear_customs(self):
        """
        Creating bills if all the HBL in the MBL are cleared customs duties.
        3 types of bill are there.1.Freight Bill,2.BIll for Us Gov.,3.Bill
        for customs clearing agent.If both the customs clearing agent
        and the freight forwarder are the same person,there would be 2 types of bills
        """
        for rec in self:
            self.hbl_line_ids.filtered(lambda r: r.state == 'received port').write({'state' : 'customs cleared'})
            if all(state == 'customs cleared' for state in self.hbl_line_ids.mapped('state')):
                self.write({'state' : 'customs cleared'})
            if not self._context.get('container_clearance', False):
                
                container_ids = self.hbl_line_ids.container_id
                container_ids.create_container_status_note(msg="Customs cleared for BOL %s" % (rec.name), user_id=self.env.user)
            if self.state in ['customs cleared','received port','received warehouse']:
                journal_domain = [
                    ('type', '=', 'purchase')
                ]
                default_journal_id = self.env['account.journal'].search(journal_domain, limit=1)
                partner_id = self.env['res.partner'].search([('us_customs','=',True)],limit=1)
                if default_journal_id:
                    c_duty_bill_id = self.env['account.move'].create({'partner_id' : partner_id.id,
                                                                      'move_type' : 'in_invoice',
                                                                      'mhbl_id' : rec.id,
                                                                      'bill_type' : 'duty',
                                                                      'journal_id' : default_journal_id.id,
                                                                      'reference' : rec.mbl_no,
                                                                      })
                    rec.prepare_invoice_lines(c_duty_bill_id)

                    if rec.freight_forwarder.id == rec.customs_agent_id.id:
                        vendor_bill = self.env['account.move'].create({'partner_id' : rec.freight_forwarder.id,
                                                                      'bill_type' :'freight_plus_process',
                                                                      'journal_id' : default_journal_id.id,
                                                                      'move_type' : 'in_invoice',
                                                                      'mhbl_id': rec.id,
                                                                      'reference' : rec.mbl_no,
                                                                       })
                        rec.prepare_invoice_lines(vendor_bill)

                    else:
                        freight_bill = self.env['account.move'].create({ 'partner_id' : rec.freight_forwarder.id,
                                                                        'bill_type' :'freight charge',
                                                                        'journal_id' : default_journal_id.id,
                                                                        'mhbl_id': rec.id,
                                                                        'move_type' : 'in_invoice',
                                                                        'reference' : rec.mbl_no,
                                                                        })

                        customs_bill = self.env['account.move'].create({'partner_id' : rec.customs_agent_id.id,
                                                                       'bill_type' :'process fee',
                                                                       'journal_id' : default_journal_id.id,
                                                                       'mhbl_id': rec.id ,
                                                                       'move_type' : 'in_invoice',
                                                                       'reference' : rec.mbl_no,
                                                                       })

                        rec.prepare_invoice_lines(freight_bill)
                        rec.prepare_invoice_lines(customs_bill)
        if self._context.get('reload', False):
            return { 'type': 'ir.actions.client', 'tag': 'reload'}


    def prepare_invoice_lines(self, bill_id):
        """
        Preparing invoice line for above said invoices.
        """

        customs_account_id  = self.env['ir.config_parameter'].sudo().get_param('customs_clearence_account_id')
#        mhbl_id = self.mhbl_id
        inv_data = []
        if bill_id.bill_type == 'duty':
            if not customs_account_id:
                raise UserError("Please Define Customs Duty account")
            duty_line = {'name': 'Customs Duty',
                         'price_unit' : self.total_duty,
                         'account_id' : int(customs_account_id),
                         'mhbl_id': self.id,
                         'move_id' : bill_id.id
                         }
            mp_fee = self.merch_process_fee
            us_customs_partner_id = bill_id.partner_id
            if mp_fee and (mp_fee < us_customs_partner_id.mp_min_limit):
                mp_fee = us_customs_partner_id.mp_min_limit
            elif mp_fee and (mp_fee > us_customs_partner_id.mp_max_limit):
                mp_fee = us_customs_partner_id.mp_max_limit


            merch_fee_line = {'name': 'Merchendise Processing Fee',
                              'price_unit' : mp_fee,
                              'account_id' : int(customs_account_id),
                              'mhbl_id': self.id,
                              'move_id' : bill_id.id
                              }

            harbour_m_fee = {'name' : 'Harbour Maintenance Fee',
                             'price_unit': self.harbour_maint_fee,
                             'account_id' : int(customs_account_id),
                             'mhbl_id' : self.id,
                             'move_id' : bill_id.id
                             }

            inv_data = [duty_line, merch_fee_line, harbour_m_fee]
            move_list = list()
            
            for inv_rec in inv_data:
                move_list.append([0,False,inv_rec])
            bill_id.invoice_line_ids = move_list

        else:
            customs_agent_id = self.customs_agent_id
            freight_forwarder_id = self.freight_forwarder

            freight_account_id = self.env['ir.config_parameter'].sudo().get_param('freight_account_id')
#            hbl_count = len(self.mapped('hbl_ids'))
            container_ids = self.hbl_line_ids.mapped('container_id')
            container_types = container_ids.mapped('container_type') #TODO
            freight_charge = sum(self.hbl_line_ids.mapped('container_id').mapped('freight_charge'))
            if bill_id.bill_type in ['process fee', 'freight_plus_process']:
                if not freight_account_id:
                    raise UserError("Please Define a Customs Clearence Account")
                entry_f_line = {'name':'Entry Fee(per MBL)',
                                'price_unit' : customs_agent_id.entry_fee,
                                'move_id': bill_id.id,
                                'account_id' : int(customs_account_id)
                                }

                doc_f_line = {'name': 'Documentation Fee(per MBL)',
                              'account_id' : int(freight_account_id),
                              'price_unit': customs_agent_id.documentation_fee,
                              'move_id' : bill_id.id
                              }
                inv_data = [entry_f_line, doc_f_line]


                if '20 feet' in container_types:
                    t_mitigan_20_line = {'name':"Traffic Mitign Fee(20' Container)",
                                         'quantity': container_types.count('20 feet'),
                                         'price_unit': customs_agent_id.t_mitigan_fee_20_cont,
                                         'account_id' : int(freight_account_id),
                                         'move_id' : bill_id.id
                                         }
                    inv_data.append(t_mitigan_20_line)

                if '40 feet' in container_types:
                    t_mitigan_40_line = {'name' : "Traffic Mitign Fee(40' Container)",
                                         'quantity' : container_types.count('40 feet'),
                                         'price_unit': customs_agent_id.t_mitigan_fee_40_cont,
                                         'account_id' : int(freight_account_id),
                                         'move_id' : bill_id.id
                                         }
                    inv_data.append(t_mitigan_40_line)

                if '45 feet' in container_types:
                    t_mitigan_45_line = {'name' : "Traffic Mitign Fee(45' Container)",
                                        'quantity' : container_types.count('45 feet'),
                                        'price_unit': customs_agent_id.t_mitigan_fee_45_cont,
                                        'account_id' : int(freight_account_id),
                                        'move_id' : bill_id.id
                                         }
                    inv_data.append(t_mitigan_45_line)

                if '40 HC' in container_types:
                    t_mitigan_40_hc_line = {'name' : "Traffic Mitign Fee(40'HC Container)",
                                            'quantity' : container_types.count('40 HC'),
                                            'price_unit': customs_agent_id.t_mitigan_fee_40_hc_cont,
                                            'account_id' : int(freight_account_id),
                                            'move_id' : bill_id.id
                                            }
                    inv_data.append(t_mitigan_40_hc_line)
            if bill_id.bill_type in ['freight_plus_process','freight charge'] :
                freight_line = {}
                if not freight_account_id:
                    raise ValidationError("Please Define Freight Account")
                cont_with_f_chrg = container_ids.mapped(lambda rec:(rec.container_type,rec.freight_charge))
                for cont_tup in cont_with_f_chrg:
                    f_line_val = freight_line.get(cont_tup, False)
                    if f_line_val:
                        f_line_val.update({'quantity' : f_line_val.get('quantity')+1})
                        continue
                    name = "Freight Charge(%s)" % (cont_tup[0]) if cont_tup[0] in ['Air Freight','LCL'] else "Freight Charge(%s Container )" % (cont_tup[0])
                    freight_line.update({cont_tup : {'name' : name,
                                 'quantity' : 1,
                                 'price_unit' : cont_tup[1],
                                 'account_id' : int(freight_account_id),
                                 'move_id' : bill_id.id
                                   }})
                isf_s_line = {'name':'ISF Importer Security Filing(per HBL)',
                              'price_unit' : freight_forwarder_id.isf_import_security,
                              'quantity': 1.0,
                              'account_id' : int(freight_account_id),
                              'move_id' : bill_id.id
                               }
                inv_data.extend(freight_line.values())
                inv_data.append(isf_s_line)
            move_list = list()
            for inv_rec in inv_data:
                move_list.append([0,False,inv_rec])
            bill_id.invoice_line_ids = move_list
        return True

    def action_view_customs_duty(self):

        action = self.env.ref('container_management.hbl_customs_duty_menu_action')
        result = action.read()[0]
        if len(self.hbl_line_ids) > 0:
            result['domain'] = "[('hbl_line_id', 'in', " + str(self.hbl_line_ids.ids) + ")]"
        return result

#    @api.multi
    def unlink(self):
        for mbl in self:
            mbl.hbl_line_ids.unlink()
            mbl.container_ids.unlink()
        return super(MasterHouseBillLading, self).unlink()
  
    def action_set_container_lines(self):
        self.ensure_one()
        return {
                'name': 'Container PO',
                'view_type': 'form',
                'view_mode': 'form',
                # 'context': {'current_id': self.id},
                'res_model': 'container.wizard',
                'view_id': self.env.ref('container_management.view_container_wizard_form').id,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }


MasterHouseBillLading()



class HouseBillLading(models.Model):
    _name = 'house.bill.lading'
    _description="House Bill Of Lading"
    _order = "id desc"


    name = fields.Char(string="Name", compute='compute_hbl_name')
    lading_no = fields.Char(string="House Bill Of Lading No", copy=False, tracking=True)
    state = fields.Selection([('draft', 'Draft'),
                              ('ready','Ready To Ship'),
                              ('in ocean', 'In Ocean'),
                              ('received port', 'Received In Port'),
                              ('customs cleared','Customs Cleared'),
                              ('received partial', 'Partaily Received in Warehouse'),
                              ('received warehouse', 'Received In Warehouse')], compute='compute_state',  index=True, copy=False, store=True, tracking=True, string="State")
    mhbl_id = fields.Many2one('master.house.bill.lading', string="Master Bill Of Lading", states={'in ocean': [('readonly', True)],
                                                                                                    'received port': [('readonly', True)],
                                                                                                    'customs cleared': [('readonly', True)],
                                                                                                    'received partial':[('readonly', True)]
                                                                                                })
    mbl_no = fields.Char(string="MBL No.")
    hbl_line_ids = fields.One2many('container.line', 'hbl_id', string="Containers", ondelete="cascade")
    customs_line_total = fields.Monetary(string="Customs Duty", compute='compute_customs_line_total', store=True)
    merch_process_fee = fields.Monetary(string="Merchendise Processing Fee", compute='compute_customs_fee')
    harbour_maint_fee = fields.Monetary(string="Harbour Maintenance Fee", compute='compute_customs_fee')
    total_duty = fields.Monetary(string="Total Duty", compute='compute_customs_fee')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self:self.env.user.company_id.currency_id)
    sequence = fields.Integer(string='Sequence', default=10)


    @api.depends('lading_no')
    def compute_hbl_name(self):
        for rec in self:
            rec.name = rec.lading_no if rec.lading_no else ""

    @api.model
    def create(self,vals):
        hbl_id = super(HouseBillLading, self).create(vals)
        mhbl_id = vals.get('mhbl_id', False)
        if mhbl_id:
            mhbl_id = self.env['master.house.bill.lading'].browse(mhbl_id)
            if mhbl_id.state == 'ready':
                hbl_id.action_ready()
        return hbl_id

    def action_clear_customs(self):
        """
        Creating bills if all the HBL in the MBL are cleared customs duties.
        3 types of bill are there.1.Freight Bill,2.BIll for Us Gov.,3.Bill
        for customs clearing agent.If both the customs clearing agent
        and the freight forwarder are the same person,there would be 2 types of bills
        """
        for rec in self:
            self.hbl_line_ids.write({'state' : 'customs cleared'})
            container_ids = rec.mapped('hbl_line_ids.container_id')
            container_ids.create_container_status_note(msg="Customs cleared for HBL %s" % (rec.name), user_id=self.env.user)
            if all(state in ['customs cleared','received partial','received warehouse'] for state in rec.mhbl_id.mapped('hbl_ids').mapped('state')):
                journal_domain = [
                    ('type', '=', 'purchase')
                ]
                default_journal_id = self.env['account.journal'].search(journal_domain, limit=1)
                partner_id = self.env['res.partner'].search([('us_customs','=',True)],limit=1)
                if default_journal_id:
                    c_duty_bill_id = self.env['account.move'].create({'partner_id' : partner_id.id,
                                                                      'move_type' : 'in_invoice',
                                                                      'mhbl_id' : rec.mhbl_id.id,
                                                                      'bill_type' : 'duty',
                                                                      'journal_id' : default_journal_id.id,
                                                                      'reference' : rec.mhbl_id.mbl_no,
                                                                      })
                    rec.prepare_invoice_lines(c_duty_bill_id)

                    if rec.mhbl_id.freight_forwarder.id == rec.mhbl_id.customs_agent_id.id:
                        vendor_bill = self.env['account.move'].create({'partner_id' : rec.mhbl_id.freight_forwarder.id,
                                                                      'bill_type' :'freight_plus_process',
                                                                      'journal_id' : default_journal_id.id,
                                                                      'move_type' : 'in_invoice',
                                                                      'mhbl_id': rec.mhbl_id.id,
                                                                      'reference' : rec.mhbl_id.mbl_no,
                                                                       })
                        rec.prepare_invoice_lines(vendor_bill)

                    else:
                        freight_bill = self.env['account.move'].create({ 'partner_id' : rec.mhbl_id.freight_forwarder.id,
                                                                        'bill_type' :'freight charge',
                                                                        'journal_id' : default_journal_id.id,
                                                                        'mhbl_id': rec.mhbl_id.id,
                                                                        'move_type': 'in_invoice',
                                                                        'reference' : rec.mhbl_id.mbl_no,
                                                                        })

                        customs_bill = self.env['account.move'].create({'partner_id' : rec.mhbl_id.customs_agent_id.id,
                                                                       'bill_type' :'process fee',
                                                                       'journal_id' : default_journal_id.id,
                                                                       'mhbl_id': rec.mhbl_id.id ,
                                                                       'move_type': 'in_invoice',
                                                                       'reference' : rec.mhbl_id.mbl_no,
                                                                       })

                        rec.prepare_invoice_lines(freight_bill)
                        rec.prepare_invoice_lines(customs_bill)
        if self._context.get('reload', False):
            return { 'type': 'ir.actions.client', 'tag': 'reload'}

    def prepare_invoice_lines(self, bill_id):
        """
        Preparing invoice line for above said invoices.
        """

        customs_account_id  = self.env['ir.config_parameter'].sudo().get_param('customs_clearence_account_id')
        mhbl_id = self.mhbl_id
        inv_data = []
        if bill_id.bill_type == 'duty':
            if not customs_account_id:
                raise UserError("Please Define Customs Duty account")
            duty_line = {'name': 'Customs Duty',
                         'price_unit' : mhbl_id.total_duty,
                         'account_id' : int(customs_account_id),
                         'mhbl_id': mhbl_id.id,
                         'move_id' : bill_id.id
                         }
            mp_fee = mhbl_id.merch_process_fee
            us_customs_partner_id = bill_id.partner_id
            if mp_fee and (mp_fee < us_customs_partner_id.mp_min_limit):
                mp_fee = us_customs_partner_id.mp_min_limit
            elif mp_fee and (mp_fee > us_customs_partner_id.mp_max_limit):
                mp_fee = us_customs_partner_id.mp_max_limit


            merch_fee_line = {'name': 'Merchendise Processing Fee',
                              'price_unit' : mp_fee,
                              'account_id' : int(customs_account_id),
                              'mhbl_id': mhbl_id.id,
                              'move_id' : bill_id.id
                              }

            harbour_m_fee = {'name' : 'Harbour Maintenance Fee',
                             'price_unit': mhbl_id.harbour_maint_fee,
                             'account_id' : int(customs_account_id),
                             'mhbl_id' : mhbl_id.id,
                             'move_id' : bill_id.id
                             }

            inv_data = [duty_line, merch_fee_line, harbour_m_fee]
            move_list = list()
            
            for inv_rec in inv_data:
                move_list.append([0,False,inv_rec])
            bill_id.invoice_line_ids = move_list

        else:
            customs_agent_id = mhbl_id.customs_agent_id
            freight_forwarder_id = mhbl_id.freight_forwarder

            freight_account_id = self.env['ir.config_parameter'].sudo().get_param('freight_account_id')
            hbl_count = len(mhbl_id.mapped('hbl_ids'))
            container_ids = mhbl_id.mapped('hbl_ids').mapped('hbl_line_ids').mapped('container_id')
            container_types = container_ids.mapped('container_type') #TODO
            freight_charge = sum(mhbl_id.mapped('hbl_ids').mapped('hbl_line_ids').mapped('container_id').mapped('freight_charge'))
            if bill_id.bill_type in ['process fee', 'freight_plus_process']:
                if not freight_account_id:
                    raise UserError("Please Define a Customs Clearence Account")
                entry_f_line = {'name':'Entry Fee(per MBL)',
                                'price_unit' : customs_agent_id.entry_fee,
                                'move_id': bill_id.id,
                                'account_id' : int(customs_account_id)
                                }

                doc_f_line = {'name': 'Documentation Fee(per MBL)',
                              'account_id' : int(freight_account_id),
                              'price_unit': customs_agent_id.documentation_fee,
                              'move_id' : bill_id.id
                              }
                inv_data = [entry_f_line, doc_f_line]


                if '20 feet' in container_types:
                    t_mitigan_20_line = {'name':"Traffic Mitign Fee(20' Container)",
                                         'quantity': container_types.count('20 feet'),
                                         'price_unit': customs_agent_id.t_mitigan_fee_20_cont,
                                         'account_id' : int(freight_account_id),
                                         'move_id' : bill_id.id
                                         }
                    inv_data.append(t_mitigan_20_line)

                if '40 feet' in container_types:
                    t_mitigan_40_line = {'name' : "Traffic Mitign Fee(40' Container)",
                                         'quantity' : container_types.count('40 feet'),
                                         'price_unit': customs_agent_id.t_mitigan_fee_40_cont,
                                         'account_id' : int(freight_account_id),
                                         'move_id' : bill_id.id
                                         }
                    inv_data.append(t_mitigan_40_line)

                if '45 feet' in container_types:
                    t_mitigan_45_line = {'name' : "Traffic Mitign Fee(45' Container)",
                                        'quantity' : container_types.count('45 feet'),
                                        'price_unit': customs_agent_id.t_mitigan_fee_45_cont,
                                        'account_id' : int(freight_account_id),
                                        'move_id' : bill_id.id
                                         }
                    inv_data.append(t_mitigan_45_line)

                if '40 HC' in container_types:
                    t_mitigan_40_hc_line = {'name' : "Traffic Mitign Fee(40'HC Container)",
                                            'quantity' : container_types.count('40 HC'),
                                            'price_unit': customs_agent_id.t_mitigan_fee_40_hc_cont,
                                            'account_id' : int(freight_account_id),
                                            'move_id' : bill_id.id
                                            }
                    inv_data.append(t_mitigan_40_hc_line)
            if bill_id.bill_type in ['freight_plus_process','freight charge'] :
                freight_line = {}
                if not freight_account_id:
                    raise ValidationError("Please Define Freight Account")
                cont_with_f_chrg = container_ids.mapped(lambda rec:(rec.container_type,rec.freight_charge))
                for cont_tup in cont_with_f_chrg:
                    f_line_val = freight_line.get(cont_tup, False)
                    if f_line_val:
                        f_line_val.update({'quantity' : f_line_val.get('quantity')+1})
                        continue
                    name = "Freight Charge(%s)" % (cont_tup[0]) if cont_tup[0] in ['Air Freight','LCL'] else "Freight Charge(%s Container )" % (cont_tup[0])
                    freight_line.update({cont_tup : {'name' : name,
                                 'quantity' : 1,
                                 'price_unit' : cont_tup[1],
                                 'account_id' : int(freight_account_id),
                                 'move_id' : bill_id.id
                                   }})
                isf_s_line = {'name':'ISF Importer Security Filing(per HBL)',
                              'price_unit' : freight_forwarder_id.isf_import_security,
                              'quantity': hbl_count,
                              'account_id' : int(freight_account_id),
                              'move_id' : bill_id.id
                               }
                inv_data.extend(freight_line.values())
                inv_data.append(isf_s_line)
            move_list = list()
            for inv_rec in inv_data:
                move_list.append([0,False,inv_rec])
            bill_id.invoice_line_ids = move_list
        return True



##    @api.multi
#    def action_clear_customs(self):
#        """
#        Creating bills if all the HBL in the MBL are cleared customs duties.
#        3 types of bill are there.1.Freight Bill,2.BIll for Us Gov.,3.Bill
#        for customs clearing agent.If both the customs clearing agent
#        and the freight forwarder are the same person,there would be 2 types of bills
#        """
#        for rec in self:
#            rec.mapped('hbl_line_ids').write({'state' : 'customs cleared'})
#            container_ids = rec.mapped('hbl_line_ids.container_id')
#            container_ids.create_container_status_note(msg="Customs cleared for HBL %s" % (rec.name), user_id=self.env.user)
##            if all(state in ['customs cleared','received partial','received warehouse'] for state in rec.mhbl_id.mapped('hbl_ids').mapped('state')):
##                journal_domain = [
##                    ('type', '=', 'purchase')
##                ]
##                default_journal_id = self.env['account.journal'].search(journal_domain, limit=1)
##                partner_id = self.env['res.partner'].search([('us_customs','=',True)],limit=1)
##                if default_journal_id:
##                    c_duty_bill_id = self.env['account.move'].create({'partner_id' : partner_id.id,
##                                                                          'move_type': 'in_invoice',
##                                                                          'mhbl_id' : rec.mhbl_id.id,
##                                                                          'bill_type' : 'duty',
##                                                                          'journal_id' : default_journal_id.id,
##                                                                          'ref' : rec.mhbl_id.mbl_no,
##                                                                          })
##                    rec.prepare_invoice_lines(c_duty_bill_id)

##                    if rec.mhbl_id.freight_forwarder.id == rec.mhbl_id.customs_agent_id.id:
##                        vendor_bill = self.env['account.move'].create({'partner_id' : rec.mhbl_id.freight_forwarder.id,
##                                                                          'bill_type' :'freight_plus_process',
##                                                                          'journal_id' : default_journal_id.id,
##                                                                          'move_type': 'in_invoice',
##                                                                          'mhbl_id': rec.mhbl_id.id,
##                                                                          'ref' : rec.mhbl_id.mbl_no,
##                                                                           })
##                        rec.prepare_invoice_lines(vendor_bill)

##                    else:
##                        freight_bill = self.env['account.move'].create({ 'partner_id' : rec.mhbl_id.freight_forwarder.id,
##                                                                            'bill_type' :'freight charge',
##                                                                            'journal_id' : default_journal_id.id,
##                                                                            'mhbl_id': rec.mhbl_id.id,
##                                                                            'move_type': 'in_invoice',
##                                                                            'ref' : rec.mhbl_id.mbl_no,
##                                                                            })

##                        customs_bill = self.env['account.move'].create({'partner_id' : rec.mhbl_id.customs_agent_id.id,
##                                                                           'bill_type' :'process fee',
##                                                                           'journal_id' :default_journal_id.id,
##                                                                           'mhbl_id': rec.mhbl_id.id ,
##                                                                           'move_type': 'in_invoice',
##                                                                           'ref' : rec.mhbl_id.mbl_no,
##                                                                           })

##                        rec.prepare_invoice_lines(freight_bill)
##                        rec.prepare_invoice_lines(customs_bill)
#        if self._context.get('reload', False):
#            return { 'type': 'ir.actions.client', 'tag': 'reload'}

##    @api.multi
#    def prepare_invoice_lines(self, bill_id):
#        """
#        Preparing invoice line for above said invoices.
#        """
##        customs_account_id  = self.env['ir.values'].get_default('container.config', 'customs_clearence_account_id')
#        customs_account_id = self.env['ir.config_parameter'].get_param('customs_clearence_account_id', '')
#        mhbl_id = self.mhbl_id
#        inv_data = []
#        if bill_id.bill_type == 'duty':
#            if not customs_account_id:
#                raise UserError("Please Define Customs Duty account")
#            duty_line = {'name':'Customs Duty',
#                         'price_unit' : mhbl_id.total_duty,
#                         'account_id' : int(customs_account_id),
#                         'mhbl_id': mhbl_id.id,
#                         'move_id' : bill_id.id
#                         }
#            mp_fee = mhbl_id.merch_process_fee
#            us_customs_partner_id = bill_id.partner_id
#            if mp_fee and (mp_fee < us_customs_partner_id.mp_min_limit):
#                mp_fee = us_customs_partner_id.mp_min_limit
#            elif mp_fee and (mp_fee > us_customs_partner_id.mp_max_limit):
#                mp_fee = us_customs_partner_id.mp_max_limit


#            merch_fee_line = {'name':'Merchendise Processing Fee',
#                              'price_unit' : mp_fee,
#                              'account_id' : int(customs_account_id),
#                              'mhbl_id': mhbl_id.id,
#                              'move_id' : bill_id.id
#                              }

#            harbour_m_fee = {'name' :'Harbour Maintenance Fee',
#                             'price_unit': mhbl_id.harbour_maint_fee,
#                             'account_id' : int(customs_account_id),
#                             'mhbl_id' : mhbl_id.id,
#                             'move_id' : bill_id.id
#                             }

#            inv_data = [duty_line, merch_fee_line, harbour_m_fee]
#            for inv_rec in inv_data:
#                self.env['account.move.line'].create(inv_rec)

#        else:
#            customs_agent_id = mhbl_id.customs_agent_id
#            freight_forwarder_id = mhbl_id.freight_forwarder
#            freight_account_id = self.env['ir.config_parameter'].get_param('freight_account_id', '')
#            hbl_count = len(mhbl_id.mapped('hbl_ids'))
#            container_ids = mhbl_id.mapped('hbl_ids').mapped('hbl_line_ids').mapped('container_id')
#            container_types = container_ids.mapped('container_type') #TODO
#            freight_charge = sum(mhbl_id.mapped('hbl_ids').mapped('hbl_line_ids').mapped('container_id').mapped('freight_charge'))
#            if bill_id.bill_type in ['process fee', 'freight_plus_process']:
#                if not freight_account_id:
#                    raise UserError("Please Define a Customs Clearence Account")
#                entry_f_line = {'name':'Entry Fee(per MBL)',
#                                'price_unit' : customs_agent_id.entry_fee,
#                                'move_id': bill_id.id,
#                                'account_id' : int(customs_account_id)
#                                }

#                doc_f_line = {'name': 'Documentation Fee(per MBL)',
#                              'account_id' : int(freight_account_id),
#                              'price_unit': customs_agent_id.documentation_fee,
#                              'move_id' : bill_id.id
#                              }
#                inv_data = [entry_f_line, doc_f_line]


#                if '20 feet' in container_types:
#                    t_mitigan_20_line = {'name':"Traffic Mitign Fee(20' Container)",
#                                         'quantity': container_types.count('20 feet'),
#                                         'price_unit': customs_agent_id.t_mitigan_fee_20_cont,
#                                         'account_id' : int(freight_account_id),
#                                         'move_id' : bill_id.id
#                                         }
#                    inv_data.append(t_mitigan_20_line)

#                if '40 feet' in container_types:
#                    t_mitigan_40_line = {'name' : "Traffic Mitign Fee(40' Container)",
#                                         'quantity' : container_types.count('40 feet'),
#                                         'price_unit': customs_agent_id.t_mitigan_fee_40_cont,
#                                         'account_id' : int(freight_account_id),
#                                         'move_id' : bill_id.id
#                                         }
#                    inv_data.append(t_mitigan_40_line)

#                if '45 feet' in container_types:
#                    t_mitigan_45_line = {'name' : "Traffic Mitign Fee(45' Container)",
#                                        'quantity' : container_types.count('45 feet'),
#                                        'price_unit': customs_agent_id.t_mitigan_fee_45_cont,
#                                        'account_id' : int(freight_account_id),
#                                        'move_id' : bill_id.id
#                                         }
#                    inv_data.append(t_mitigan_45_line)

#                if '40 HC' in container_types:
#                    t_mitigan_40_hc_line = {'name' : "Traffic Mitign Fee(40'HC Container)",
#                                            'quantity' : container_types.count('40 HC'),
#                                            'price_unit': customs_agent_id.t_mitigan_fee_40_hc_cont,
#                                            'account_id' : int(freight_account_id),
#                                            'move_id' : bill_id.id
#                                            }
#                    inv_data.append(t_mitigan_40_hc_line)
#            if bill_id.bill_type in ['freight_plus_process','freight charge'] :
#                freight_line = {}
#                if not freight_account_id:
#                    raise ValidationError("Please Define Freight Account")
#                cont_with_f_chrg = container_ids.mapped(lambda rec:(rec.container_type,rec.freight_charge))
#                for cont_tup in cont_with_f_chrg:
#                    f_line_val = freight_line.get(cont_tup, False)
#                    if f_line_val:
#                        f_line_val.update({'quantity' : f_line_val.get('quantity')+1})
#                        continue
#                    name = "Freight Charge(%s)" % (cont_tup[0]) if cont_tup[0] in ['Air Freight','LCL'] else "Freight Charge(%s Container )" % (cont_tup[0])
#                    freight_line.update({cont_tup : {'name' : name,
#                                 'quantity' : 1,
#                                 'price_unit' : cont_tup[1],
#                                 'account_id' : int(freight_account_id),
#                                 'move_id' : bill_id.id
#                                   }})
#                isf_s_line = {'name':'ISF Importer Security Filing(per HBL)',
#                              'price_unit' : freight_forwarder_id.isf_import_security,
#                              'quantity': hbl_count,
#                              'account_id' : int(freight_account_id),
#                              'move_id' : bill_id.id
#                               }
#                inv_data.extend(freight_line.values())
#                inv_data.append(isf_s_line)
#            for inv_rec in inv_data:
#                self.env['account.move.line'].create(inv_rec)
#        return True

    @api.depends('hbl_line_ids.line_customs_id')
    def compute_customs_line_total(self):
        for rec in self:
            c_lines = rec.hbl_line_ids.mapped('line_customs_id')
            customs_total = 0.0
            hts_code_list = c_lines.mapped(lambda line : list(line.hts_ids.mapped('code')))
            hts_code_group_by = itertools.groupby(sorted(hts_code_list))
            for code_list, group in hts_code_group_by:
                hts_code_ids = c_lines.filtered(lambda line:line.hts_ids.mapped('code') == code_list).mapped('hts_ids')
                purchase_total = sum(c_lines.filtered(lambda line:line.hts_ids.mapped('code') == code_list).mapped('price_total'))
                for hts_id in hts_code_ids:
                    purchase_total = round(purchase_total)
                    total = rec.currency_id.round((purchase_total * hts_id.percentage) / 100)
                    extra_duty = 0.0
                    if hts_id.extra_duty_applicable:
                        qty = sum(c_lines.filtered(lambda line:line.hts_ids.mapped('code') == code_list).mapped('quantity'))
                        extra_duty = (truncate((qty / hts_id.quantity),1) * hts_id.extra_duty)
                    customs_total += (total + rec.currency_id.round(extra_duty))
            rec.customs_line_total = customs_total
            return True

#    @api.multi
    def compute_customs_fee(self):
        """
        Compute Merchendise Processing Fee,Harbour Maintenanance Charge,
        and Customs duty for HBL.
        """
        customs_partner_id = self.env['res.partner'].search([('us_customs','=',True)], limit=1)
        merch_p_fee = customs_partner_id.merch_process_fee
        harbour_m_fee = customs_partner_id.harbour_maint_fee
        for rec in self:
            c_line_ids = rec.hbl_line_ids.mapped('line_customs_id')
            m_fee = 0.0
            h_fee = 0.0

            if merch_p_fee and  harbour_m_fee:
                hts_code_list = c_line_ids.mapped(lambda line : list(line.hts_ids.mapped('code')))
                hts_code_group_by = itertools.groupby(sorted(hts_code_list))
                for code_list, group in hts_code_group_by:
                    purchase_total = sum(c_line_ids.filtered(lambda line:line.hts_ids.mapped('code') == code_list).mapped(lambda line:line.quantity * line.unit_price))
                    purchase_total = round(purchase_total)
                    m_fee += rec.currency_id.round((purchase_total*merch_p_fee)/100)
                    h_fee += rec.currency_id.round((purchase_total * harbour_m_fee)/100)
                rec.merch_process_fee = m_fee
                rec.harbour_maint_fee = h_fee
            rec.total_duty = (rec.merch_process_fee + rec.harbour_maint_fee + rec.customs_line_total) or 0.0



    @api.depends('hbl_line_ids.state', 'hbl_line_ids.hbl_id')
#    @api.one
    def compute_state(self):
        state_list = [hbl_line.state for hbl_line in self.hbl_line_ids]
        if not self.hbl_line_ids or all(map(lambda rec:rec == 'draft',state_list)):
            self.state = 'draft'
        elif all(map(lambda rec:rec == 'ready',state_list)):
            self.state = 'ready'
        elif all(map(lambda rec:rec == 'in ocean',state_list)):
            self.state = 'in ocean'
        elif all(map(lambda rec:rec == 'received port',state_list)):
            self.state = 'received port'
        elif set(['review']).issubset(set(state_list)):
            self.state = 'customs cleared'
        elif all(map(lambda rec:rec == 'customs cleared',state_list)):
            self.state = 'customs cleared'
        elif all(map(lambda rec:rec == 'received warehouse',state_list)):
            self.state ='received warehouse'
        elif set(['received warehouse']).issubset(set(state_list)):
            self.state = 'received partial'
        else:
            self.state = 'draft'

#    @api.multi
    def action_ready(self):
        """
        Change HBL state to 'ready' if the Quantity loaded in different container
        for that purchase line is less than the quantity ordered.
        """
        purchase_lines = self.mapped('hbl_line_ids').mapped('purchase_line')
        hbl_line_ids = self.mapped('hbl_line_ids')
        for line in purchase_lines:
            qty_to_transfer = line.qty_received + sum(hbl_line_ids.filtered(lambda p_line : p_line.purchase_line.id == line.id).mapped('qty_to_load'))
            if line.product_qty < qty_to_transfer :
                raise ValidationError("""The total number of quantities loaded in different containers for purchase line '%s' is %s.This exceeded purchase line's ordered quantity(%s).""" % (line.name, qty_to_transfer, line.product_qty))
        hbl_line_ids.write({'state' : 'ready'})

#    @api.multi
    def action_draft(self):
        self.mapped('hbl_line_ids').write({'state' : 'draft'})

#    @api.multi
    def action_receive_in_port(self):
        self.mapped('hbl_line_ids').write({'state' : 'received port'})

#    @api.multi
    def action_move_to_ocean(self):
        hbl_lines =  self.mapped('hbl_line_ids')
        hbl_lines.write({'state' : 'in ocean'})

#    @api.multi
    def calculate_quantity_to_receive(self):
        """
        Calculate the quantity that we want to receive while
        validating the Delivery order.
        """
        hbl_ids = self
        po_lines = []
        hbl_lines = hbl_ids.mapped('hbl_line_ids').sorted(key=lambda line:line.purchase_line.id)
        for line in hbl_lines:
            if po_lines and po_lines[-1].get('p_line').id == line.purchase_line.id:
                dict_line = po_lines[-1]
                dict_line.update({'qty' : dict_line['qty'] + line.qty_to_load})
            else:
                po_lines.append({'p_line' : line.purchase_line,
                                 'qty' : line.qty_to_load,
                                 'po_id' : line.po_id,
                                 'product_id' : line.purchase_line.product_id.id,
                                 'hbl_id' : line.hbl_id
                                 })

        return po_lines

#    @api.multi
    def validate_to_ocean(self):
        """
        Receive the quantity in ocean.and compute the sum of all the quantities
        loaded in differnt container for that purchase line,and write
        it in delivery order.Then validate delivery order.
        """
        self.action_ready()
        hbl_ids = self
        po_lines = hbl_ids.calculate_quantity_to_receive()
        picking = []
#        oc_loc_id = self.env['stock.warehouse'].search([('code', '=', 'OC')]).lot_stock_id
        for line in po_lines:
            p_order = line.get('po_id')
            picking_id = p_order.picking_ids.filtered(lambda rec:rec.state not in ['draft','cancel','done'] and rec.warehouse_type == 'ocean')
            if not picking_id:
                raise ValidationError("Shipment for purchase order %s either in 'Draft','Cancel' or 'Done' status.This can't be moved to ocean" % (p_order.name))
            if len(picking_id) == 1:
                picking_move_id = picking_id.mapped('move_ids_without_package').filtered(lambda rec:rec.product_id.id == line.get('product_id'))
                if picking_move_id.product_qty < line.get('qty'):
                    raise ValidationError("""Shipped  Qty for the product '%s(%s)' is exceeded Ordered Qty.Please check Qty loaded in the Container(s).""" % (line.get('p_line').name,line.get('p_line').order_id.name))
                picking_move_id.write({'quantity_done' : line.get('qty')})
                picking.append(picking_id)
        picking = set(picking)
        for picking_id in picking:
            result=picking_id.button_validate()
            picking_id.write({'carrier' : ("BOL # %s")%(line.get('hbl_id',False) and line.get('hbl_id',False).lading_no),
                              'bill_of_lading' : line.get('hbl_id',False) and line.get('hbl_id',False).name
                               })
            if result and result.get('res_id', False):
                res_id = self.env['stock.backorder.confirmation'].browse(result['res_id'])
                res_id._process()
            purchase_id = picking_id.purchase_id
#            invoice_id = picking_id.invoice_id
#            if invoice_id and invoice_id.state == 'draft' :
#                invoice_id.write({
#                    'reference': '%s / %s' % (line.get('hbl_id').mbl_no, purchase_id.name),
#                    'date_invoice': line.get('hbl_id').mhbl_id.etd,
#                })
#                invoice_id.action_invoice_open()

            if picking_id.move_lines  and picking_id.warehouse_type == 'ocean' and line.get('hbl_id').mhbl_id.etd:
#                move_date = line.get('hbl_id').mhbl_id.etd.strftime("%Y-%m-%d") + " 12:00:00"
                move_date = str(line.get('hbl_id').mhbl_id.etd) + " 12:00:00"
                picking_id.move_lines.write({'date' : datetime.strptime(move_date, DEFAULT_SERVER_DATETIME_FORMAT)})

        hbl_ids.action_move_to_ocean()
        hbl_ids.mapped('hbl_line_ids').get_duty_percentage()
        return True


#    @api.multi
    def action_view_customs_duty(self):

        action = self.env.ref('container_management.hbl_customs_duty_menu_action')
        result = action.read()[0]
        if len(self.hbl_line_ids) > 0:
            result['domain'] = "[('hbl_line_id', 'in', " + str(self.hbl_line_ids.ids) + ")]"
        return result


#    @api.multi
    def unlink(self):
        for hbl in self:
            hbl.hbl_line_ids.unlink()
        return super(HouseBillLading, self).unlink()


HouseBillLading()
