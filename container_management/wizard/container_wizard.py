from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ContainerWizard(models.TransientModel):
    _name = "container.wizard"

    po_ids = fields.Many2many('purchase.order', string="Purchase order")
    container_id = fields.Many2one('container.container', string="Container No", ondelete='cascade')
    
   

    def set_lines(self):
        bols = self.env['master.house.bill.lading'].browse(self.env.context.get('active_ids'))
        bols.hbl_line_ids.unlink()
        cont_vals = []
        for orders in self.po_ids:
            for each_po in orders:
                for lines in each_po.order_line:
                    cont_vals.append(
                        (0, 0, {'po_id': each_po.id, 'purchase_line': lines.id,
                                'ordered_qty': lines.product_qty, 'qty_to_load': lines.product_qty,'container_id':self.container_id.id,
                                }))
        bols.write({'hbl_line_ids': cont_vals})
        return True
