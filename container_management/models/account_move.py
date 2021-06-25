# -*- coding: utf-8 -*-

from odoo import api, fields, models
from lxml import etree, html
#from odoo.osv.orm import setup_modifiers


class AccountMove(models.Model):
    _inherit = "account.move"

    bill_type = fields.Selection([('freight charge','Freight Forward Charge'),('duty','Customs Duty'),('process fee','Process Fee'),('freight_plus_process','Freight + Processing Fee')], string="Bill Type")
    mhbl_id = fields.Many2one('master.house.bill.lading', string="Master Bill Of Lading")
    reference = fields.Char(states={'draft': [('readonly', False)],'open': [('readonly', False)]})

    @api.onchange('mhbl_id')
    def onchange_mhbl_id(self):
        if self.mhbl_id:
            self.reference = self.mhbl_id.mbl_no

#    @api.model
#    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
#        """
#        Overriding field_view_get to hide product_id,Account analytical id,
#        Account tags, Tax Ids in vendor bills of container management module.
#        the corresponding column canot hide with
#        invisible attrs.
#        """
#        res = super(AccountMove, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)

#        if view_type == 'form':
#            doc = etree.XML(res['fields']['invoice_line_ids']['views']['tree']['arch'])
#            product_node = doc.xpath("//field[@name='product_id']")[0]
#            tax_line_node = doc.xpath("//field[@name='tax_ids']")[0]
#            uom_node = doc.xpath("//field[@name='product_uom_id']")[0]
#            analytical_node = doc.xpath("//field[@name='analytic_account_id']")[0]
#            anal_tag_node = doc.xpath("//field[@name='analytic_tag_ids']")[0]
#            node_list = [product_node, tax_line_node, uom_node, analytical_node, anal_tag_node]
#            is_vendor_bill = self._context.get('cont_bills', False)
#            if is_vendor_bill:
#                for node in node_list:
#                    doc.remove(node)
#                res['fields']['invoice_line_ids']['views']['tree']['arch'] = etree.tostring(doc)
#                doc = etree.XML(res['arch'])
#                res['arch'] = etree.tostring(doc)
#        return res


AccountMove()


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    mhbl_id = fields.Many2one('master.house.bill.lading', related="move_id.mhbl_id")
    name = fields.Text(string='Description', required=False)

AccountMoveLine()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
