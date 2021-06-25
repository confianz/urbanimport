
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models,api,_


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_freight_forwarder = fields.Boolean(string="Freight Forwarder")
    is_customs_agents = fields.Boolean(string="Customs Clearing Agents")
    hbl_id = fields.Char(string="House Bill Of Lading")
    hbl_count = fields.Integer(compute='_compute_hbl_count', string='# of MBL')
    documentation_fee = fields.Monetary(string="Documentation Fee(per MBL)")
    isf_import_security = fields.Monetary(string="ISF Importer Security Filing(per HBL)")
    entry_fee = fields.Monetary(string="Entry Fee(per MBL)")
    t_mitigan_fee_40_cont = fields.Monetary(string="40' Container")
    t_mitigan_fee_20_cont = fields.Monetary(string="20' Container")
    t_mitigan_fee_45_cont = fields.Monetary(string="45' Container")
    t_mitigan_fee_40_hc_cont = fields.Monetary(string="40'HC Container")
    us_customs = fields.Boolean(string="US Customs and Border Protection")
    merch_process_fee = fields.Float(string = "Merchandise Processing Fee(%)", digits='Product Price')
    harbour_maint_fee = fields.Float(string = "Harbour Maintenance Fee(%)", digits='Product Price')
    mp_min_limit = fields.Monetary(string="MPF-Min Limit")
    mp_max_limit = fields.Monetary(string="MPF-Max Limit")

    def _compute_hbl_count(self):
        """
        Compute the count of Master bill of lading which is associated
        with the freight forwarder.
        """
        hbl_data = self.env['master.house.bill.lading'].read_group(domain=[('freight_forwarder', 'child_of', self.ids)],
                                                      fields=['freight_forwarder'], groupby=['freight_forwarder'])
        partner_child_ids = self.read(['child_ids'])
        mapped_data = dict([(m['freight_forwarder'][0], m['freight_forwarder_count']) for m in hbl_data])
        for partner in self:
            partner_ids = list(filter(lambda r: r['id'] == partner.id, partner_child_ids))[0]
            partner_ids = [partner_ids.get('id')] + partner_ids.get('child_ids')
            partner.hbl_count = sum(mapped_data.get(child, 0) for child in partner_ids)

#    def _compute_hbl_count(self):
#        # retrieve all children partners and prefetch 'parent_id' on them
#        all_partners = self.search([('id', 'child_of', self.ids)])
#        all_partners.read(['parent_id'])

#        mhbl_data = self.env['master.house.bill.lading'].read_group(domain=[('freight_forwarder','in', all_partners.ids)],
#                                                      fields=['freight_forwarder'], groupby=['freight_forwarder'])
#        partners = self.browse()
#        for group in mhbl_data:
#            partner = self.browse(group['freight_forwarder'][0])
#            while partner:
#                if partner in self:
#                    partner.hbl_count += group['partner_id_count']
#                    partners |= partner
#                partner = partner.parent_id
#        (self - partners).hbl_count = sum(mapped_data.get(child, 0) for child in partner_ids)

    #@api.onchange('is_freight_forwarder','is_customs_agents')
    #def onchange_freight_forwarder(self):
        #if self.is_freight_forwarder or self.is_customs_agents:
            #self.customer_rank = 0
            #self.supplier_rank = 1

ResPartner()
