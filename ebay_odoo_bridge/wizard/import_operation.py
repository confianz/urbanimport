# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2019-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import models, fields, api
from odoo.addons.odoo_multi_channel_sale.ApiTransaction import Transaction
import logging
_logger = logging.getLogger(__name__)


class ImportOperation(models.TransientModel):
    _inherit = 'import.operation'

    object = fields.Selection(
        selection_add=[
            ('business.policies.mappings', 'Business Policy')
        ]
    )
    ebay_filter_type = fields.Selection(
        string='Ebay Filter Type',
        selection=[
            ('all', 'All'),
            ('date_range', 'Date Range'),
            ('id', 'By ID'),
        ],
        default='all',
        required=True,
    )
    ebay_object_id = fields.Char('Ebay Object ID')
    ebay_updated_at_min = fields.Datetime('Ebay Updated From', default=lambda self: self.wk_from_date)
    ebay_updated_at_max = fields.Datetime('Ebay Updated Till', default=lambda self: self.wk_to_date)
    ebay_level_limit = fields.Integer('Level Limit', default=1)

    ebay_category = fields.Many2one(
        comodel_name='channel.category.mappings',
        string="Ebay Category",
    )
    ebay_order_status = fields.Selection(
        [('All', 'All'), ('Active', 'Active'), ('Completed', 'Completed'), ('Inactive', 'InActive')],
        string='Ebay Order Status',
        default="Completed",
        help="The field is used to retrieve orders that are in a specific state.")

    @api.onchange("object")
    def _onchange_object(self):
        res = {}
        ebay = ('ecom_store', '=', 'ebay')
        if self.object in ["sale.order", "product.template"]:
            self.ebay_filter_type = "date_range"
        if self.object == "product.category":
            domain = [ebay, ('leaf_category', '=', False)]
            ids = self.env["channel.category.mappings"].search(domain).ids
            res["domain"] = {"ebay_category": [('id', 'in', ids)]}
        if self.object == "product.template":
            ids = self.env["channel.category.mappings"].search([ebay]).ids
            res["domain"] = {"ebay_category": [('id', 'in', ids)]}
        return res

    def ebay_get_filter(self):
        kw = {
            'filter_type':   self.ebay_filter_type,
            'order_status':    self.ebay_order_status,
            'updated_at_min':  self.ebay_updated_at_min,
            'updated_at_max':  self.ebay_updated_at_max,
        }
        if self.ebay_filter_type == 'id':
            kw['object_id'] = self.ebay_object_id
        if self.ebay_level_limit:
            kw['limit'] = self.ebay_level_limit
        if self.ebay_category:
            kw['ebay_category'] = self.ebay_category.store_category_id
        return kw

    etsy_detail_level = fields.Char(
        string='Default Detail Level',
        size=50,
        required=1,
        readonly=1,
        invisible=0,
        default='ReturnAll')

    def import_with_filter(self, **kw):
        if self.channel=='ebay':
            return EbayTransaction(channel=self.channel_id).import_data(**kw)
        else:
            return Transaction(channel=self.channel_id).import_data(**kw)


class EbayTransaction(Transaction):

    def import_data(self, object, **kw):
        if object == 'business.policies.mappings':
            success_ids = []
            error_ids = []
            create_ids = []
            update_ids = []
            kw.update(
                page_size=self.instance.api_record_limit
            )
            msg = ''
            try:
                while True:
                    feeds = False
                    data_list, kw = getattr(
                        self.instance, 'import_{}'.format(self.channel))(object, **kw)
                    if data_list:
                        kw['last_id'] = data_list[-1].get('store_id')
                    s_ids, e_ids, feeds = self.create_business_policies(
                        data_list)

                    self._cr.commit()
                    _logger.info(f'~~~~{len(s_ids)} feeds committed~~~~')
                    _logger.info(f"~~~~Latest Id: {kw.get('last_id')}~~~~")
                    success_ids.extend(s_ids)
                    error_ids.extend(e_ids)
                    if self.evaluate_feed and feeds:
                        mapping_ids = feeds.with_context(
                            get_mapping_ids=True).import_items()
                        create_ids.extend(
                            [mapping.id for mapping in mapping_ids.get('create_ids')])
                        update_ids.extend(
                            [mapping.id for mapping in mapping_ids.get('update_ids')])
                        self._cr.commit()
                        _logger.info('~~~~Created feeds are evaluated~~~~')
                    if len(data_list) < kw.get('page_size'):
                        break
            except Exception as e:
                msg = f'Something went wrong: `{e.args[0]}`'
                _logger.exception(msg)

            if not msg:
                if success_ids:
                    msg += f"<p style='color:green'>{success_ids} imported.</p>"
                if error_ids:
                    msg += f"<p style='color:red'>{error_ids} not imported.</p>"
                if create_ids:
                    msg += f"<p style='color:blue'>{create_ids} created.</p>"
                if update_ids:
                    msg += f"<p style='color:blue'>{update_ids} updated.</p>"
                if kw.get('last_id'):
                    msg += f"<p style='color:brown'>Last Id: {kw.get('last_id')}.</p>"
            if not msg:
                msg = "<p style='color:red'>No records found for applied filter.</p>"
            return self.display_message(msg)
        else:
            return super(EbayTransaction, self).import_data(object, **kw)

    def create_business_policies(self, data_list):
        success_ids, error_ids = [], []
        BusinessPolicy = self.env['business.policies.mappings']
        mappings = self.env['business.policies.mappings']
        for policy_data in data_list:
            try:
                ebay_policy = BusinessPolicy.create(policy_data)
            except:
                ebay_policy = False
            if ebay_policy:
                mappings += ebay_policy
                success_ids.append(policy_data.get('policy_id'))
            else:
                error_ids.append(policy_data.get('policy_id'))
        return success_ids, error_ids, []
