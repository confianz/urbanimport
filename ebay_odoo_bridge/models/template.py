# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2019-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo.exceptions import ValidationError
from odoo import models, fields, api
from odoo.addons.odoo_multi_channel_sale.tools import _unescape

import logging
_logger = logging.getLogger(__name__)


EBAY_CONDITION_IDS = [
    ('1000', 'NEW'),
    ('1500', 'NEW OTHER(without tags, without box)'),
    ('1750', 'NEW WITH DEFECTS'),
    ('2000', 'MANUFACTURER REFURBISHED'),
    ('2500', 'SELLER REFURBISHED'),
    ('2750', 'LIKE NEW'),
    ('3000', 'USED or PRE-OWNED'),
    ('4000', 'VERY GOOD'),
    ('5000', 'GOOD'),
    ('6000', 'ACCEPTABLE'),
    ('7000', 'FOR PARTS OR NOT WORKING'),

]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def create(self, vals):
        context = dict(self._context or {})
        if context.get('ebay'):
            if vals.get('name'):
                vals['name'] = _unescape(vals['name'])
            if vals.get('description'):
                vals['description'] = _unescape(vals['description'])
            if vals.get('description_sale'):
                vals['description_sale'] = _unescape(vals['description_sale'])
        template_id = super(ProductTemplate, self).create(vals)
        if context.get('ebay'):
            variant_ids_ids = self.browse(template_id.id).product_variant_ids
            temp = {'template_id': template_id}
            if len(variant_ids_ids) == 1:
                temp['product_id'] = variant_ids_ids[0].id
            else:
                temp['product_id'] = -1

            self._cr.commit()
            return temp
        return template_id

    def write(self, vals):
        context = dict(self._context or {})
        if context.get('ebay'):
            if vals.get('name'):
                vals['name'] = _unescape(vals['name'])
            if vals.get('description'):
                vals['description'] = _unescape(vals['description'])
            if vals.get('description_sale'):
                vals['description_sale'] = _unescape(vals['description_sale'])
        return super(ProductTemplate, self).write(vals)

    def _get_default_category_id(self):
        if self._context.get('categ_id') or self._context.get('default_categ_id'):
            return self._context.get('categ_id') or self._context.get('default_categ_id')
        category = self.env.ref(
            'product.product_category_all', raise_if_not_found=False)
        return category and category.id or False

    ebay_product_url = fields.Char(
        string='Ebay Url'
    )
    ebay_description_html = fields.Text(
        string='Ebay HTML Description'
    )
    ebay_Brand = fields.Char(
        string="Brand",
        default="Unbranded",
        help="Ebay Brand: Choose specifc brand name based on primary category assigned or create your own"
    )
    ebay_MPN = fields.Char(
        string="MPN",
		help="Ebay Manufacturer Part Number, it enables buyer to easily find particular part"
    )
    use_ebay_specifics = fields.Boolean(
        string="Use Ebay Specifics",
        help="By enabling this feature you can use the Ebay specifics on the products"
    )
    ebay_specifics = fields.Text(
        string="Ebay Product Specifics")
    show_ebay_specifics_values = fields.Text(
        string="Ebay Specifics Values"
    )
    ebay_overide_default_config = fields.Boolean(
        string="Overide Default Config",
        help="You can overide the default product configuration by enabling this field and add the values specific to this product."
    )
    ebay_condition_id = fields.Selection(
        EBAY_CONDITION_IDS,
        string='Product Condition',
        help='Condition of the product to be exported. It depends on ebay primary category',
        default="1000",
    )
    ebay_business_policies = fields.Selection(
        [('existing', 'Existing'), ('custom', 'Custom')],
        string='Business Policies to be used',
        default="custom",
        help="If you want to use the existing payment ebay policy. Import all the existing policies and select one of them."
    )
    ebay_existing_payment_policy = fields.Many2one(
        comodel_name="business.policies.mappings",
        string="Payment Policy",
        domain=[('policy_type', '=', 'PAYMENT')],
        help="Select the payment Policy you wnt to use for creating a listing on ebay"
    )
    ebay_existing_shipping_policy = fields.Many2one(
        comodel_name="business.policies.mappings",
        string="Shipping Policy",
        domain=[('policy_type', '=', 'SHIPPING')],
        help="Select the shipping Policy you wnt to use for creating a listing on ebay"
    )
    ebay_existing_return_policy = fields.Many2one(
        comodel_name="business.policies.mappings",
        string="Return Policy",
        domain=[('policy_type', '=', 'RETURN_POLICY')],
        help="Select the return Policy you wnt to use for creating a listing on ebay"
    )
    ebay_return_accepted_option = fields.Selection(
        [('ReturnsAccepted', 'ReturnsAccepted'),
         ('ReturnsNotAccepted', 'ReturnsNotAccepted')],
        string='Returns Accepted Option',
        default="ReturnsAccepted",
        help="Weather to accept the returns for this producr or not"
    )
    ebay_return_within_option = fields.Selection(
        [('Days_3', '3 Days'), ('Days_7', '7 Days'), ('Days_10', '10 Days'),
         ('Days_14', '14 Days'), ('Months_1', '1 Month'), ('Days_60', '2 Months')],
        default="Days_10",
        string='Returns Within Options',
        help="Return the the product within how much time"
    )
    ebay_shipping_cost_paid_by = fields.Selection(
        [('Buyer', 'Buyer'), ('Seller', 'Seller')],
        string='Shipping CostPaid By Option',
        default="Buyer",
        help="Who will pay the shipping cost of the return"
    )
    ebay_return_description = fields.Text(
        'Additional Information',
        help="Add some Additional information regarding your Return Policy",
        default="This is a test return description"
    )
    ebay_shipping_service = fields.Many2one(
        comodel_name='channel.shipping.mappings',
        string='Shipping Method',
        domain=[('ecom_store', '=', 'ebay')],
        help="Shipping service for exporting the products to odoo.These must be fetched from ebay before exporting the product to odoo."
    )
    ebay_shipping_cost = fields.Float(
        string='Shipping Service Cost',
        help="Cost of the shipping service used with the Product"
    )
    ebay_shipping_additional_cost = fields.Float(
        string="Shipping Service Additional Cost",
        help="The cost of shipping each additional item if the same buyer purchases multiple quantity of the same line item. This field is required when creating a multiple-quantity, fixed-price listing."
    )
    ebay_shipping_priority = fields.Selection(
        [('1', '1'), ('2', '2'), ('3', '3'), ('4', '4')],
        string='Shipping Service Priority',
        default="1",
        help="This integer value controls the order (relative to other shipping services) in which the corresponding ShippingService will appear in the View Item and Checkout page."
    )
    ebay_dispatch_time_max = fields.Selection(
        [('0', 'Same Day'), ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'), ('10', '10'),
         ('20', '20'), ('30', '30')],
        string='DispatchTimeMax',
        help="Specifies the maximum number of business days the seller commits to for preparing an item to be shipped after receiving a cleared payment."
    )
    ebay_payment_method = fields.Many2one(
        comodel_name='channel.account.journal.mappings',
        string='Payment Method',
        domain=[('ecom_store', '=', 'ebay')],
        help="Identifies the payment method (such as PayPal) that the seller will accept when the buyer pays for the item."
    )
    ebay_payment_method_related = fields.Char(
        related='ebay_payment_method.name',
        string="Payment_method"
    )
    paypal_email_address = fields.Char(
        string='PayPalEmailAddress',
        default="test@paypal.com",
        help="Valid PayPal email address for the PayPal account that the seller will use if they offer PayPal as a payment method for the listing. eBay uses this to identify the correct PayPal account when the buyer pays via PayPal during the checkout process"
    )
    ebay_max_names = fields.Integer(
        string="Item Specifics Names",
        default=30,
        help="Maxium number of item specifics to be imported. Default value is 30."
    )
    ebay_max_values_per_name = fields.Integer(
        string="Item Specific Values",
        default=25,
        help="Maxium number of values to be imported for each item Specifics.Default value is 25."
    )

    def import_ebay_product_category_specifics(self):
        category_id = False
        instance_id = False
        if self.channel_category_ids:
            for channel_categ_id in self.channel_category_ids:
                if channel_categ_id.instance_id.channel == 'ebay' and channel_categ_id.extra_category_ids:
                    categs_ids = channel_categ_id.extra_category_ids[0].channel_mapping_ids
                    for categ_id in categs_ids:
                        if categ_id.ecom_store == 'ebay':
                            category_id = categs_ids[0]
                            instance_id = channel_categ_id.instance_id
                            break
        if category_id:
            res = self.env['channel.category.mappings'].getCategorySpecificsapiCall(
                category_id=category_id, channel_id=instance_id, temp_id=self)
            self.ebay_specifics = res.get('name_value_list')
            self.show_ebay_specifics_values = res.get('all_value_lists')
            return self.env['multi.channel.sale'].display_message(res.get('message'))
        else:
            raise ValidationError(
                'Please select the ebay category for this product')


class ExtraCategories(models.Model):
    _inherit = 'extra.categories'

    @api.onchange('instance_id')
    def change_domain(self):
        li = []
        if self.instance_id.channel == 'ebay':
            category_ids_list = self.env['channel.category.mappings'].search(
                [('channel_id', '=', self.instance_id.id), ('leaf_category', '=', True)])
        else:
            category_ids_list = self.env['channel.category.mappings'].search(
                [('channel_id', '=', self.instance_id.id)])
        if category_ids_list:
            for i in category_ids_list:
                li.append(i.odoo_category_id)
        domain = {'domain': {'extra_category_ids': [('id', 'in', li)]}}
        return domain

    @api.model
    def get_category_list(self):
        li = []
        if self.instance_id.channel == 'ebay':
            category_ids_list = self.env['channel.category.mappings'].search(
                [('channel_id', '=', self.instance_id.id), ('leaf_category', '=', True)])
        else:
            category_ids_list = self.env['channel.category.mappings'].search(
                [('channel_id', '=', self.instance_id.id)])
        if category_ids_list:
            for i in category_ids_list:
                li.append(i.odoo_category_id)
        return li
