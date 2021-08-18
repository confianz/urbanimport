from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ContainerWizard(models.TransientModel):
    _name = "container.wizard"

    po_ids = fields.Many2many('purchase.order', string="Purchase order")
    container_id = fields.Many2one('container.container', string="Container No", ondelete='cascade')

    def set_lines(self):
        bols = self.env['master.house.bill.lading'].browse(self.env.context.get('active_ids'))
        cnt_lines = self.env['container.line']
        bols.hbl_line_ids.unlink()
        cont_vals = []
        msg = ''
        for orders in self.po_ids:
            for each_po in orders:
                for lines in each_po.order_line:
                    exist_lines = cnt_lines.search([('purchase_line', '=', lines.id)])
                    tot_ordered_qty = 0
                    tot_qty_to_load = 0
                    for exist_line in exist_lines:
                        tot_ordered_qty += exist_line.ordered_qty
                        tot_qty_to_load += exist_line.qty_to_load
                    if not exist_lines:
                        cont_vals.append(
                            (0, 0, {'po_id': each_po.id, 'purchase_line': lines.id,
                                    'ordered_qty': lines.product_qty, 'qty_to_load': lines.product_qty,
                                    'container_id': self.container_id.id,
                                    }))
                    elif exist_lines and tot_ordered_qty != 0:
                        cont_vals.append(
                            (0, 0, {'po_id': each_po.id, 'purchase_line': lines.id,
                                    'ordered_qty': lines.product_qty, 'qty_to_load': lines.product_qty - tot_qty_to_load,
                                    'container_id': self.container_id.id,
                                    }))
                    else:
                        msg = msg + 'MBL-' + str(exist_lines[0].mbl_id.mbl_no) + ' ' + exist_lines[0].po_id.name + '-' + exist_lines[0].purchase_line.product_id.name + ' '
        bols.write({'hbl_line_ids': cont_vals})
        if msg:
            bols.message_post(
                body=('Exception :- These products are already loaded in other Master Bill of Lading \n %s') % (msg),
                subtype_id=self.env.ref('mail.mt_note').id)
        return True
