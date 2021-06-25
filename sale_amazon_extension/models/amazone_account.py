# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models, _
from odoo.addons.sale_amazon.models import mws_connector as mwsc


_logger = logging.getLogger(__name__)
# True if the tax amount is included in the sales price
MARKETPLACES_WITH_TAX_INCLUDED = {
    'A2EUQ1WTGCTBG2': False,  # amazon.ca
    'A1AM78C64UM0Y8': False,  # amazon.com.mx
    'ATVPDKIKX0DER': False,   # amazon.com
    'A1PA6795UKMFR9': True,   # amazon.de
    'A1RKKUPIHCS9HS': True,   # amazon.es
    'A13V1IB3VIYZZH': True,   # amazon.fr
    'APJ6JRA9NG5V4': True,    # amazon.it
    'A1F83G8C2ARO7P': True,   # amazon.co.uk
    'A1805IZSGTT6HS': True,   # amazon.nl
}


class AmazonAccount(models.Model):
    _inherit = 'amazon.account'

    partner_id = fields.Many2one('res.partner', "Partner")
    warehouse_id = fields.Many2one('stock.warehouse', "Warehouse")

    def _get_product(self, product_code, default_xmlid, default_name, default_type, fallback=True):
        """
        Find a product by its internal reference with a fallback to a default product.
        :param product_code: the code of the item to match with the internal reference of a product
        :param default_xmlid: the xmlid of the default product to use as fallback
        :param default_name: the name of the default product to use as fallback
        :param default_type: the type of the default product to use as fallback
        :param fallback: whether a fallback to the default product is needed
        """
        self.ensure_one()
        edi_record = self.env['edi.customer'].search([('sku_product_id', '=', product_code),
                                                              ('partner_id', '=', self.partner_id.id)], limit=1)
        product = edi_record.product_id.product_variant_id
        if not product and fallback:  # Fallback to the default product
            product = self.env.ref('sale_amazon.%s' % default_xmlid, raise_if_not_found=False)
        if not product and fallback:  # Restore the default product if it was deleted
            product = self.env['product.product']._restore_data_product(
                default_name, default_type, default_xmlid)
        return product

    def _process_order(self, order_data, orders_api):
        """ Create a sale order from the data of an Amazon order. """
        self.ensure_one()
        amazon_order_ref = mwsc.get_string_value(order_data, 'AmazonOrderId')
        items_data = []

        # Order items are fetched one batch at a time.
        # If the fetched batch is full, a next_token is generated and can be used
        # to fetch the next batch with the same query params as the previous one.
        has_next, next_token = True, None

        # Because the rate limits of 'ListOrderItems' and 'ListOrderItemsByNextToken' are shared,
        # it is impossible to anticipate query throttling by the API. If the rate limit is reached,
        # the synchronization of all remaining orders is postponed to the next run.
        rate_limit_reached = False
        sync_failure = False
        error_message = _("An error was encountered when synchronizing Amazon order items.")
        while has_next and not rate_limit_reached:
            items_data_batch, next_token, rate_limit_reached = mwsc.get_items_data(
                orders_api, amazon_order_ref, error_message)
            items_data += items_data_batch
            has_next = bool(next_token)

        if not rate_limit_reached:
            try:
                with self.env.cr.savepoint():
                    # Create the sale order if needed and if the status is not 'Canceled'
                    order, order_found, amazon_status = self._get_order(
                        order_data, items_data, amazon_order_ref)
                    amazon_product_included = order._context.get('amazon_product')
            except Exception as error:
                sync_failure = True
                _logger.exception(error)
            else:
                if amazon_status == 'Canceled' and order_found and order.state != 'cancel':
                    order.with_context(canceled_by_amazon=True).action_cancel()
                    _logger.info("canceled sale.order with amazon_order_ref %s for "
                                 "amazon.account with id %s" % (amazon_order_ref, self.id))
                elif not order_found and order:  # New order created
                    if order.amazon_channel == 'fba':
                        if not amazon_product_included:
                            self._generate_stock_moves(order)
                    elif order.amazon_channel == 'fbm':
                        if not amazon_product_included:
                            order.with_context(mail_notrack=True).action_done()
                    _logger.info("synchronized sale.order with amazon_order_ref %s for "
                                 "amazon.account with id %s" % (amazon_order_ref, self.id))
                elif order_found:  # Order already sync
                    _logger.info("ignored already sync sale.order with amazon_order_ref %s for "
                                 "amazon.account with id %s" % (amazon_order_ref, self.id))
                else:  # Combination of status and fulfillment channel not handled
                    _logger.info("ignored %s amazon order with reference %s for amazon.account "
                                 "with id %s" % (amazon_status.lower(), amazon_order_ref, self.id))
        return amazon_order_ref, rate_limit_reached, sync_failure

    def _get_order(self, order_data, items_data, amazon_order_ref):
        """ Find or create a sale order based on Amazon data. """
        self.ensure_one()
        status = mwsc.get_string_value(order_data, 'OrderStatus')
        fulfillment_channel = mwsc.get_string_value(order_data, 'FulfillmentChannel')

        order = self.env['sale.order'].search([('amazon_order_ref', '=', amazon_order_ref)], limit=1)
        order_found = bool(order)
        if not order_found and (
                (fulfillment_channel == 'AFN' and status == 'Shipped')
                or (fulfillment_channel == 'MFN' and status == 'Unshipped')):
            currency_code = mwsc.get_currency_value(order_data, 'OrderTotal')
            purchase_date = mwsc.get_date_value(order_data, 'PurchaseDate')
            shipping_code = mwsc.get_string_value(order_data, 'ShipServiceLevel')

            # The order is created in state 'sale' to generate a picking if fulfilled by merchant
            # and in state 'done' to generate no picking if fulfilled by Amazon
            state = 'done' if fulfillment_channel == 'AFN' else 'sale'
            shipping_product = self._get_product(
                shipping_code, 'shipping_product', 'Shipping', 'service')
            currency = self.env['res.currency'].with_context(active_test=False).search(
                [('name', '=', currency_code)], limit=1)
            pricelist = self._get_pricelist(currency)
            contact_partner, delivery_partner = self._get_partners(order_data, amazon_order_ref)
            fiscal_position_id = self.env['account.fiscal.position'].with_context(
                force_company=self.company_id.id).get_fiscal_position(
                contact_partner.id, delivery_partner.id)
            fiscal_position = self.env['account.fiscal.position'].browse(fiscal_position_id)

            order_lines_vals = self._process_order_lines(
                order_data, items_data, shipping_code, shipping_product, currency, fiscal_position)
            amazon_product = self.env.ref('sale_amazon.%s' % 'default_product', raise_if_not_found=False)
            amazon_product_id = amazon_product and amazon_product.id or 0
            amazon_product_context = False
            carrier = False
            for line in order_lines_vals:
                product_id = line.get('product_id')
                if amazon_product_id and amazon_product_id == product_id:
                    state = 'draft'
                    amazon_product_context = True
            warehouse_id =False
            if fulfillment_channel == 'AFN':
                warehouse_id = self.warehouse_id.id
            else:
                carrier = self.env['delivery.carrier'].search([('delivery_type', '=', 'ups'), ('ups_default_service_type', '=', '03')])
                warehouse = self.env['stock.warehouse'].search([('warehouse_type', '=', 'sub_warehouse')], limit=1)
                if warehouse:
                    warehouse_id = warehouse.id
            order = self.env['sale.order'].with_context(mail_create_nosubscribe=True, amazon_product=amazon_product_context).create({
                'origin': 'Amazon Order %s' % amazon_order_ref,
                'state': state,
                'date_order': purchase_date,
                'partner_id': contact_partner.id,
                'pricelist_id': pricelist.id,
                'order_line': [(0, 0, order_line_vals) for order_line_vals in order_lines_vals],
                'invoice_status': 'no',
                'partner_shipping_id': delivery_partner.id,
                'require_signature': False,
                'require_payment': False,
                'fiscal_position_id': fiscal_position_id,
                'company_id': self.company_id.id,
                'user_id': self.user_id.id,
                'team_id': self.team_id.id,
                'carrier_id': carrier and carrier.id or False,
                'is_amazon_order': True,
                'warehouse_id': warehouse_id,
                'client_order_ref': amazon_order_ref,
                'amazon_order_ref': amazon_order_ref,
                'amazon_channel': 'fba' if fulfillment_channel == 'AFN' else 'fbm',
            })
        return order, order_found, status

    def _process_order_lines(
            self, order_data, items_data, shipping_code, shipping_product, currency, fiscal_pos):
        """ Return a list of sale order line vals based on Amazon order items data. """

        def _get_order_line_vals(**kwargs):
            """ Convert and complete a dict of values to comply with fields of sale_order_line. """
            _subtotal = kwargs.get('subtotal', 0)
            _quantity = kwargs.get('quantity', 1)
            return {
                'name': kwargs.get('description', ''),
                'product_id': kwargs.get('product_id'),
                'price_unit': _subtotal / _quantity,
                'tax_id': [(6, 0, [])],
                'product_uom_qty': _quantity,
                'discount': (kwargs.get('discount', 0) / _subtotal) * 100 if _subtotal else 0,
                'display_type': kwargs.get('display_type', False),
                'amazon_item_ref': kwargs.get('amazon_item_ref'),
                'amazon_offer_id': kwargs.get('amazon_offer_id'),
            }

        self.ensure_one()
        marketplace_api_ref = mwsc.get_string_value(order_data, 'MarketplaceId')
        new_order_lines_vals = []  # List of dict of values of new order lines
        for item_data in items_data:
            sku = mwsc.get_string_value(item_data, 'SellerSKU')
            main_condition = mwsc.get_string_value(item_data, 'ConditionId')
            sub_condition = mwsc.get_string_value(item_data, 'ConditionSubtypeId')
            quantity = mwsc.get_integer_value(item_data, 'QuantityOrdered')
            sales_price = mwsc.get_amount_value(item_data, 'ItemPrice')
            tax_amount = mwsc.get_amount_value(item_data, 'ItemTax')

            offer = self._get_offer(order_data, sku)
            product_taxes = offer.product_id.taxes_id.filtered(
                lambda t: t.company_id.id == self.company_id.id)
            taxes = fiscal_pos.map_tax(product_taxes) if fiscal_pos else product_taxes
            subtotal = sales_price - tax_amount if MARKETPLACES_WITH_TAX_INCLUDED.get(
                marketplace_api_ref, False) else sales_price
            subtotal = self._recompute_subtotal(subtotal, tax_amount, taxes, currency, fiscal_pos)

            description_template = "[%s] %s" \
                if not main_condition or main_condition.lower() == 'new' \
                else _("[%s] %s\nCondition: %s - %s")
            description_fields = (sku, mwsc.get_string_value(item_data, 'Title')) \
                if not main_condition or main_condition.lower() == 'new' \
                else (sku, mwsc.get_string_value(item_data, 'Title'), main_condition, sub_condition)
            new_order_lines_vals.append(_get_order_line_vals(
                product_id=offer.product_id.id,
                description=description_template % description_fields,
                subtotal=subtotal,
                tax_ids=taxes.ids,
                quantity=quantity,
                discount=mwsc.get_amount_value(item_data, 'PromotionDiscount'),
                amazon_item_ref=mwsc.get_string_value(item_data, 'OrderItemId'),
                amazon_offer_id=offer.id))

            if mwsc.get_string_value(item_data, 'IsGift', 'false') == 'true':
                gift_wrap_code = mwsc.get_string_value(item_data, 'GiftWrapLevel')
                gift_wrap_price = mwsc.get_amount_value(item_data, 'GiftWrapPrice')
                if gift_wrap_code and gift_wrap_price != 0:
                    gift_wrap_product = self._get_product(
                        gift_wrap_code, 'default_product', 'Amazon Sales', 'consu')
                    gift_wrap_product_taxes = gift_wrap_product.taxes_id.filtered(
                        lambda t: t.company_id.id == self.company_id.id)
                    gift_wrap_taxes = fiscal_pos.map_tax(gift_wrap_product_taxes) \
                        if fiscal_pos else gift_wrap_product_taxes
                    gift_wrap_tax_amount = mwsc.get_amount_value(item_data, 'GiftWrapTax')
                    gift_wrap_subtotal = gift_wrap_price - gift_wrap_tax_amount \
                        if MARKETPLACES_WITH_TAX_INCLUDED.get(marketplace_api_ref, False) \
                        else gift_wrap_price
                    gift_wrap_subtotal = self._recompute_subtotal(
                        gift_wrap_subtotal, gift_wrap_tax_amount, gift_wrap_taxes, currency,
                        fiscal_pos)
                    new_order_lines_vals.append(_get_order_line_vals(
                        product_id=gift_wrap_product.id,
                        description=_("[%s] Gift Wrapping Charges for %s") % (
                            gift_wrap_code, offer.product_id.name),
                        subtotal=gift_wrap_subtotal,
                        tax_ids=gift_wrap_taxes.ids))
                gift_message = mwsc.get_string_value(item_data, 'GiftMessageText')
                if gift_message:
                    new_order_lines_vals.append(_get_order_line_vals(
                        description=_("Gift message:\n%s") % gift_message,
                        display_type='line_note'))

            if shipping_code:
                shipping_price = mwsc.get_amount_value(item_data, 'ShippingPrice')

                shipping_product_taxes = shipping_product.taxes_id.filtered(
                    lambda t: t.company_id.id == self.company_id.id)
                shipping_taxes = fiscal_pos.map_tax(shipping_product_taxes) if fiscal_pos \
                    else shipping_product_taxes
                shipping_tax_amount = mwsc.get_amount_value(item_data, 'ShippingTax')
                shipping_subtotal = shipping_price - shipping_tax_amount \
                    if MARKETPLACES_WITH_TAX_INCLUDED.get(marketplace_api_ref, False) \
                    else shipping_price
                shipping_subtotal = self._recompute_subtotal(
                    shipping_subtotal, shipping_tax_amount, shipping_taxes, currency, fiscal_pos)
                new_order_lines_vals.append(_get_order_line_vals(
                    product_id=shipping_product.id,
                    description=_("[%s] Delivery Charges for %s") % (
                        shipping_code, offer.product_id.name),
                    subtotal=shipping_subtotal,
                    tax_ids=shipping_taxes.ids,
                    discount=mwsc.get_amount_value(item_data, 'ShippingDiscount')))

        return new_order_lines_vals

    def _get_partners(self, order_data, amazon_order_ref):
        """ Find or create two partners of respective type contact and delivery from Amazon data. """
        self.ensure_one()
        anonymized_email = mwsc.get_string_value(order_data, 'BuyerEmail')
        buyer_name = mwsc.get_string_value(order_data, 'BuyerName')
        shipping_address_name = mwsc.get_string_value(order_data, ('ShippingAddress', 'Name'))
        street = mwsc.get_string_value(order_data, ('ShippingAddress', 'AddressLine1'))
        address_line2 = mwsc.get_string_value(order_data, ('ShippingAddress', 'AddressLine2'))
        address_line3 = mwsc.get_string_value(order_data, ('ShippingAddress', 'AddressLine3'))
        street2 = "%s %s" % (address_line2, address_line3) \
            if address_line2 or address_line3 else None
        zip_code = mwsc.get_string_value(order_data, ('ShippingAddress', 'PostalCode'))
        city = mwsc.get_string_value(order_data, ('ShippingAddress', 'City'))
        country_code = mwsc.get_string_value(order_data, ('ShippingAddress', 'CountryCode'))
        state_code = mwsc.get_string_value(order_data, ('ShippingAddress', 'StateOrRegion'))
        phone = mwsc.get_string_value(order_data, ('ShippingAddress', 'Phone'), None)
        is_company = mwsc.get_string_value(
            order_data, ('ShippingAddress', 'AddressType'), 'Residential') == 'Commercial'
        country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        if phone and 'ext' in phone:
            phone_split = phone.split('ext')
            phone = phone_split and phone_split[0]
        if not phone:
            phone = self.company_id.phone
        state = self.env['res.country.state'].search(
            [('country_id', '=', country.id), '|', ('code', '=ilike', state_code),
             ('name', '=ilike', state_code)], limit=1)
        # if not state:
        #     state = self.env['res.country.state'].with_context(tracking_disable=True).create({
        #         'country_id': country.id,
        #         'name': state_code,
        #         'code': state_code
        #     })
        # If personal information of the customer are not provided because of API restrictions,
        # all concerned fields are left blank as well as the amazon email to avoid matching an
        # anonymized partner with the same customer if personal info are later provided again.
        anonymized_customer = not all([buyer_name, shipping_address_name, street or street2])
        new_partner_vals = {
            'street': street if not anonymized_customer else None,
            'street2': street2 if not anonymized_customer else None,
            'zip': zip_code,
            'city': city,
            'country_id': country.id,
            'state_id': state.id,
            'phone': phone,
            'customer_rank': 1 if not anonymized_customer else 0,
            'company_id': self.company_id.id,
            'amazon_email': anonymized_email,
        }

        # If personal info are not anonymized, a contact partner is created only for new customers.
        # If personal info are anonymized, a contact partner is always created to avoid matching
        # a non-anonymized partner previously created for the current customer.
        contact = self.partner_id
        if not contact:
            contact_name = buyer_name if not anonymized_customer \
                else "Amazon Customer # %s" % amazon_order_ref
            contact = self.env['res.partner'].with_context(tracking_disable=True).create({
                'name': contact_name,
                'is_company': is_company,
                'is_amazon_customer': True,
                **new_partner_vals,
            })
        # The contact partner acts as delivery partner if the address is either anonymous or
        # strictly equal to that of the contact partner. If not, a delivery partner is required.
        delivery = contact if anonymized_customer \
                              or (contact.name == shipping_address_name and contact.street == street
                                  and (not contact.street2 or contact.street2 == street2)
                                  and contact.zip == zip_code and contact.city == city
                                  and contact.country_id.id == country.id
                                  and contact.state_id.id == state.id) else None
        if not delivery:
            delivery = self.env['res.partner'].search(
                [('parent_id', '=', contact.id), ('type', '=', 'delivery'),
                 ('name', '=', shipping_address_name), ('street', '=', street),
                 '|', ('street2', '=', False), ('street2', '=', street2), ('zip', '=', zip_code),
                 ('city', '=', city), ('country_id', '=', country.id), ('state_id', '=', state.id),
                 '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)], limit=1)
        if not delivery:
            delivery = self.env['res.partner'].with_context(tracking_disable=True).create({
                'name': shipping_address_name,
                'type': 'delivery',
                'is_amazon_customer': True,
                'parent_id': contact.id,
                **new_partner_vals,
            })
        return contact, delivery
