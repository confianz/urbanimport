# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.osv import expression


class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    @api.model
    def _sync_pickings(self, account_ids=()):
        """
        Notify Amazon to confirm orders whose pickings are marked as done. Called by cron.
        We assume that the combined set of pickings (of all accounts) to be synchronized will always
        be too small for the cron to be killed before it finishes synchronizing all pickings.
        If provided, the tuple of account ids restricts the pickings waiting for synchronization
        to those whose account is listed. If it is not provided, all pickings are synchronized.
        :param account_ids: the ids of accounts whose pickings should be synchronized
        """
        pickings_by_account = {}
        for picking in self.search([('amazon_sync_pending', '=', True)]):
            if picking.sale_id.order_line:
                offer = picking.sale_id.order_line[0].amazon_offer_id
                account = offer and offer.account_id  # Offer can be deleted before the cron update
                if not account or (account_ids and account.id not in account_ids):
                    continue
                pickings_by_account.setdefault(account, self.env['stock.picking'])
                if picking.picking_type_id.code != 'outgoing': # sync only OUT picking in 3 step delivery.
                    continue
                pickings_by_account[account] += picking
        for account, pickings in pickings_by_account.items():
            pickings._confirm_shipment(account)


class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    @api.model
    def _search_rule(self, route_ids, product_id, warehouse_id, domain):
        """ First find a rule among the ones defined on the procurement
        group, then try on the routes defined for the product, finally fallback
        on the default behavior
        """
        if warehouse_id:
            domain = expression.AND([['|', ('warehouse_id', '=', warehouse_id.id), ('warehouse_id', '=', False)], domain])
        Rule = self.env['stock.rule']
        res = self.env['stock.rule']
        if route_ids:
            res = Rule.with_context(active_test=True).search(expression.AND([[('route_id', 'in', route_ids.ids)], domain]), order='route_sequence, sequence', limit=1)
        if not res:
            product_routes = product_id.route_ids | product_id.categ_id.total_route_ids
            if product_routes:
                res = Rule.with_context(active_test=True).search(expression.AND([[('route_id', 'in', product_routes.ids)], domain]), order='route_sequence, sequence', limit=1)
        if not res and warehouse_id:
            warehouse_routes = warehouse_id.route_ids
            if warehouse_routes:
                res = Rule.with_context(active_test=True).search(expression.AND([[('route_id', 'in', warehouse_routes.ids)], domain]), order='route_sequence, sequence', limit=1)
        return res

