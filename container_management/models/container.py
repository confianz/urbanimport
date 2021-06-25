# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models,api,_
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, date


class Container(models.Model):
    _name = 'container.container'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Container "
    _order ='priority desc'



    READONLY_STATES = {'in ocean': [('readonly', True)],
                      'received port': [('readonly', True)],
                      'customs cleared': [('readonly', True)],
                      'review' :  [('readonly', True)],
                      'received warehouse' :  [('readonly', True)],
                      'partial clearence' : [('readonly', True)],
                      'received partial' :[('readonly', True)],
                      }


    container_no = fields.Char(string="Container No.")
    name = fields.Char(string="Name", related="container_no")
    container_lines = fields.One2many('container.line','container_id', string="Container Lines", states=READONLY_STATES)
    stock_move_count = fields.Integer(string="Stock Moves", compute='compute_stock_move_count')
    container_type = fields.Selection([('20 feet',"20' Standard"),('40 feet',"40' Standard"),("40 HC", "40' High Cube"),("45 feet","45' High Cube"),('Air Freight', "Air Freight"),('LCL', "LCL")], string="Container Type", states = {'customs cleared': [('readonly', True)],
           'review' :  [('readonly', True)],
           'received partial' :[('readonly', True)],
           'partial clearence' : [('readonly', True)],
           'received warehouse' :  [('readonly', True)]
           })

    mhbl_id = fields.Many2one('master.house.bill.lading', string="Master Bill Of Lading", compute='compute_mhbl_id', inverse='_set_container_line_mhbl', store=True, states=READONLY_STATES)
    state = fields.Selection([('draft', 'Draft'),
                              ('ready','Ready To Ship'),
                             ('in ocean', 'In Ocean'),
                             ('received port', 'Received In Port'),
                             ('customs cleared','Customs Cleared'),
                             ('review','Review Shipment'),
                             ('partial clearence', 'Partial Clearence'),
                             ('received partial','Partaily Received WH'),
                             ('received warehouse', 'Received In Warehouse')], compute='_compute_state',  readonly=True, index=True, copy=False, default='draft', store=True, tracking = True, string="State")
    freight_charge = fields.Float(string="Freight Charge", states = {'customs cleared': [('readonly', True)],
                                                                    'review' :  [('readonly', True)],
                                                                    'partial clearence' : [('readonly', True)],
                                                                    'received partial' :[('readonly', True)],
                                                                    'received warehouse' :  [('readonly', True)]
                                                                    })
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self:self.env.user.company_id.currency_id)
    priority = fields.Boolean(string="High Priority")
    note_ids = fields.One2many('container.status.note', 'container_id', string="Tracking Updates")
    last_note = fields.Char(string="Latest Updates", compute='compute_last_note')
    freight_forwarder_id = fields.Many2one(related='mhbl_id.freight_forwarder', store=True, string='Freight Forwarder')
    cont_product_sku = fields.Char(related="container_lines.purchase_line.product_id.default_code", string="Product Internal Reference")
#    cont_product_customer_sku = fields.Char(related="container_lines.purchase_line.product_id.customer_product_value_ids.customer_sku", string="Product Customer SKU")
    port_date = fields.Date(related="mhbl_id.port_date", store=True, string="Estimated At Port Date")

#    @api.model
#    def compute_last_note(self):
#        for rec in self:
#            note_ids = rec.note_ids.sorted(key=lambda container : container.status_date)
#            if note_ids:
#                print ('dateeeeeeeee', type(note_ids[-1].status_date), note_ids[-1].status_date.strftime('%m/%d/%Y'))
#                rec.last_note = '%s : %s' % (note_ids[-1].status_date.strftime('%m/%d/%Y'), note_ids[-1].name)
#            else:
#                rec.last_note = ""

    @api.model
    def compute_last_note(self):
        for rec in self:
            note_ids = rec.note_ids.sorted(key=lambda container : container.status_date)
            rec.last_note = '%s : %s' % (str(note_ids[-1].status_date), note_ids[-1].name)  if note_ids else ""

    @api.depends('container_lines','container_lines.mbl_id')
    def compute_mhbl_id(self):
        for rec in self:
            mhbl_id = rec.container_lines.mapped('mbl_id')
            if len(mhbl_id) == 1:
                rec.mhbl_id = mhbl_id

    @api.depends('container_lines.state', 'container_lines.container_id')
    def _compute_state(self):
        for rec in self:
            state_list = [hbl_line.state for hbl_line in rec.container_lines]
            if not self.container_lines or all(state == 'draft' for state in state_list):
                rec.state = 'draft'
            elif all(state == 'ready' for state in state_list):
                rec.state = 'ready'
            elif all(state == 'in ocean' for state in state_list):
                rec.state = 'in ocean'
            elif all(state == 'received port' for state in state_list):
                rec.state = 'received port'
            elif all(state == 'customs cleared' for state in state_list):
                rec.state = 'customs cleared'
            elif all(state == 'received warehouse' for state in state_list):
                rec.state ='received warehouse'
            elif set(['received warehouse']).issubset(set(state_list)):
                rec.state = 'received partial'
            elif set(['received port','customs cleared']).issubset(set(state_list)):
                rec.state = 'partial clearence'
            elif all(state == 'review' for state in state_list):
                rec.state = 'review'
            else:
                rec.state = 'draft'

    def _set_container_line_mhbl(self):
        for container in self:
            for line in container.container_lines:
                line.state = container.mhbl_id.state
#                if container.mhbl_id.hbl_ids.ids and line.hbl_id.id not in container.mhbl_id.hbl_ids.ids:
#                    line.hbl_id = False
#                    raise ValidationError("Please Set the Bill of lading in Container Lines according MBL")

#    @api.multi
    def compute_stock_move_count(self):
        """
        Function that compute number of stock moves for
        that particular container have.
        """
        for container in self:
            stock_moves = self.env['stock.move'].search([('container_ids','in',[container.id])])
            container.stock_move_count = len(stock_moves)

#    @api.multi
    def action_review_shipment(self):
        self.mapped('container_lines').write({'state' : 'review'})
        self.create_container_status_note(msg="Review Shipment", user_id=self.env.user)

#    @api.multi
    def action_ready_to_pick(self):
        self.mapped('container_lines').write({'state' : 'customs cleared'})
        self.create_container_status_note(msg="Ready To Pick", user_id=self.env.user)

#    @api.multi
    def write(self,vals):
        msg = ""
        if 'priority' in vals:
            if vals['priority']:
                msg = 'Marked High Priority'
            else:
                msg = "Removed High Priority"
            self.create_container_status_note(msg=msg, user_id=self.env.user)
        res = super(Container,self).write(vals)
        return res


#    @api.multi
    def action_view_stock_moves(self):
        """
        Return stock moves action to view the stock moves
        associated with the Container.
        """
        action = self.env.ref('stock.stock_move_action')
        result = action.read()[0]
        result['domain'] = "[('container_ids', 'in', " + str([self.id]) + ")]"
        return result

#    @api.multi
    def create_container_status_note(self, msg='', user_id=None):
        container_note_obj = self.env['container.status.note']
        for container in self:
            date_today = date.today()
            container_note_obj.create({'status_date': date_today,
                                       'name' : msg,
                                       'user_id' : user_id and user_id.id or False,
                                       'container_id' : container.id
                                       })

    def unlink(self):
        container_states = self.mapped('state')
        if 'draft' in container_states or 'ready' in container_states or not container_states:
            return super(Container, self).unlink()
        raise UserError("You can Delete Container only at 'Draft' or 'Ready To Ship' state")

Container()


class ContainerLines(models.Model):
    _name = 'container.line'
    _description = "Container Line"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    po_id = fields.Many2one('purchase.order', string="Purchase Order")
    purchase_line = fields.Many2one('purchase.order.line', string="Order Item")
    etd = fields.Date(compute='compute_etd', string="Ship Date", store=True)
    ordered_qty = fields.Integer(string="Order / Remaining Quantity", compute='compute_ordered_remain_qty')
    qty_to_load = fields.Float(string="Qty To Load", digits='Product Unit of Measure')
    container_id = fields.Many2one('container.container', string="Container No", ondelete='cascade')
    hbl_id = fields.Many2one('house.bill.lading', string="House Bill Of Lading")
    mbl_id = fields.Many2one('master.house.bill.lading',string="Master Bill Of Lading")
    state = fields.Selection([('draft', 'Draft'),
                              ('ready','Ready To Ship'),
                              ('in ocean', 'In Ocean'),
                              ('received port', 'Received In Port'),
                              ('customs cleared','Customs Cleared'),
                              ('review','Review Shipment'),
                              ('received partial','Partaily Received WH'),
                              ('received warehouse', 'Received In Warehouse')],  index=True, copy=False,tracking = True,store=True, default='draft', string="State")
    qty_transferred_to_wh = fields.Float(string="Qty Transferred to WH")
    line_customs_id = fields.Many2one('hbl.customs.duty', string="Line Customs Duty")
    date_at_ocean = fields.Date(related="mbl_id.date_at_ocean", store=True)
    date_planned = fields.Datetime(related="purchase_line.date_planned")
    sequence = fields.Integer(string='Sequence', default=10)

    @api.onchange('po_id')
    def onchange_po_id(self):
        self.purchase_line = False


    @api.depends('purchase_line','purchase_line.qty_loaded_in_cont','qty_to_load')
    def compute_ordered_remain_qty(self):
        for rec in self:
            qty = 0
            if rec.purchase_line:
                qty = (rec.purchase_line.product_qty - rec.purchase_line.qty_received) - rec.purchase_line.qty_loaded_in_cont
            rec.ordered_qty = qty

    @api.model
    def create(self, vals):
        mbl_id = self.env['master.house.bill.lading'].browse(vals.get('mbl_id',False))
        if mbl_id:
            vals['state'] = mbl_id.state
        res = super(ContainerLines, self).create(vals)
        return res

#    @api.multi
#    def action_clear_customs(self):
#        hbl_line_ids = self.filtered(lambda rec:rec.state == 'received port')
#        hbl_line_ids.write({'state' : 'customs cleared'})

    @api.depends('mbl_id.etd')
    def compute_etd(self):
        for rec in self:
            rec.etd = rec.mbl_id.etd if rec.mbl_id else False

    def action_clear_customs(self):
        self.write({'state' : 'customs cleared'})
        self.container_id.create_container_status_note(msg="Customs cleared for BOL %s" % (self.mbl_id.name), user_id=self.env.user)
        if all(state in ['customs cleared','received partial','received warehouse'] for state in self.mbl_id.mapped('hbl_line_ids').mapped('state')):
            self.mbl_id.with_context(container_clearance=True).action_clear_customs()

#    @api.multi
    def action_received_in_warehouse(self):
        self.write({'state' : 'received warehouse'})

        if self._context.get('post_track_msg', False):
            warehouse = self._context.get('warehouse','')
            for line in self:
                msg ="%s-%s Received in Warehouse %s" %(line.po_id.name,line.purchase_line.product_id.display_name,warehouse)
                line.container_id.create_container_status_note(msg=msg, user_id=self.env.user)

#    @api.multi
#    def compute_customs_duty_line(self):
#        for line in self:
#            line_customs_id = self.env['hbl.customs.duty'].search([('hbl_line_id','=',line.id)])
#            if line_customs_id:
#                line.line_customs_id = line_customs_id.id


#    @api.multi
    def get_duty_percentage(self):
        """
         Compute duty percentage of each purchase line in the container.
         This is done while receiving the container in ocean.
         Create a line in hbl.customs.duty model,this line
         can be refer from the corresponding HBL.
        """
        container_line_ids = self
        hbl_customs_obj = self.env['hbl.customs.duty']
        for line in container_line_ids:
            p_line = line.purchase_line
            #Get the supplier from product by using po supplier id.
            product_supplier_id = p_line.product_id.seller_ids.filtered(lambda rec:rec.name.id == p_line.partner_id.id and rec.hts_codes_ids)
            #Get HTS code of the supplier
            hts_codes_ids = product_supplier_id and product_supplier_id[0].hts_codes_ids or False
            if hts_codes_ids:
                percentage = sum(hts_codes_ids.mapped('percentage'))
                line_customs_id = hbl_customs_obj.create({'hbl_line_id' : line.id,
                                        'hts_ids': [(6,_, hts_codes_ids.ids)],
                                        'duty_percentage': percentage,
                                        'quantity' : line.qty_to_load,
                                        'unit_price' : p_line.price_unit
                                        })
                line.write({'line_customs_id' : line_customs_id.id})


ContainerLines()

class ContainerStatusNotes(models.Model):
    _name = 'container.status.note'
    _description = "Container Status Note"

    name = fields.Text(string="Updates")
    status_date = fields.Date(string="Status Date", default=datetime.today())
    container_id = fields.Many2one('container.container', string="Container")
    user_id = fields.Many2one('res.users', string="Updated By", default=lambda self: self.env.user.id)
    sequence = fields.Integer(string='Sequence', default=10)

ContainerStatusNotes()

