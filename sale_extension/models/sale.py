# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import models, fields, api, _
from datetime import datetime, timedelta

EBAY_DATEFORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'


def _ebay_parse_date(s):  # should be fromisoformat starting with datetime 3.7
    return datetime.strptime(s, EBAY_DATEFORMAT)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_ebay_order = fields.Boolean("Is Ebay order")
    delivery_address = fields.Text("Delivery Address Text")
    delivery_created_id = fields.Many2one('res.partner', string='Delivery Created')

    # @api.onchange('partner_id')
    # def onchange_partner_id(self):
    #     super(SaleOrder, self).onchange_partner_id()
    #     self.update({
    #         'partner_shipping_id': False,
    #     })

    @api.onchange('delivery_address')
    def on_change_delivery_address(self):
        try:
            delivery_address = self.delivery_address
            if delivery_address:
                if not self.partner_id:
                    raise UserError("Please select the Customer before entering the delivery address.")
                non_empty_lines = [line for line in delivery_address.split('\n') if line.strip() != ""]
                no_of_lines = len([line for line in delivery_address.split('\n') if line.strip() != ""])
                # print('non_empty_linesnon_empty_linesnon_empty_lines', non_empty_lines)
                # print('no_of_linesno_of_linesno_of_linesno_of_lines', no_of_lines)

                if no_of_lines == 4:
                    company_name = non_empty_lines[0]
                    name = non_empty_lines[1]
                    street = non_empty_lines[2]
                    city, state_code, zipcode = [(non_empty_lines[3].split(','))[i] for i in (0, 1, 2)]
                    if self.delivery_created_id and self.delivery_created_id.company_contact_id:
                        company_contact_id = self.delivery_created_id.company_contact_id
                        self.delivery_created_id.company_contact_id.write({'name': name})
                    else:
                        company_contact_id = self.env['res.partner'].create(
                            {'name': name, 'type': 'contact', 'company_type': 'person'})
                    vals = {'company_type': 'company', 'company_contact_id': company_contact_id.id,
                            'name': company_name}
                elif no_of_lines == 3:
                    name = non_empty_lines[0]
                    street = non_empty_lines[1]
                    city, state_code, zipcode = [(non_empty_lines[2].split(','))[i] for i in (0, 1, 2)]
                    vals = {'company_type': 'person', 'name': name}
                else:
                    raise UserError("Please check the number of lines entered.")
                zipcode = str(zipcode.strip())
                state = self.env['res.country.state'].sudo().search(
                    [('code', '=', str(state_code.strip())), ('country_id', '=', self.partner_id.country_id.id)],
                    limit=1)
                if not state:
                    raise UserError("State Not found for the given State Code.")
                vals.update({
                    'type': 'delivery',
                    'street': street,
                    'city': city,
                    'state_id': state.id,
                    'zip': zipcode,
                    'parent_id': self.partner_id.id,
                    'country_id': self.partner_id.country_id.id
                })
                if self.delivery_created_id:
                    self.delivery_created_id.write(vals)
                    if self.delivery_created_id.company_contact_id:
                        self.delivery_created_id.company_contact_id.write({'parent_id': self.delivery_created_id.id})
                        self.partner_shipping_id = self.delivery_created_id.company_contact_id.id
                    else:
                        self.partner_shipping_id = self.delivery_created_id.id
                else:
                    new_partner_shipping_id = self.env['res.partner'].create(vals)
                    self.delivery_created_id = new_partner_shipping_id.id
                    if self.delivery_created_id.company_contact_id:
                        self.delivery_created_id.company_contact_id.write({'parent_id': self.delivery_created_id.id})
                        self.partner_shipping_id = self.delivery_created_id.company_contact_id.id
                    else:
                        self.partner_shipping_id = new_partner_shipping_id.id
        except Exception as e:
            raise UserError(_('Please check the Address format \n %s' % e))

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        if self.bigcommerce_store_id:
            invoice = self._create_invoices()
            invoice.action_post()
            Journal = self.env['account.journal'].search(
                [('type', '=', 'bank')], limit=1)
            payment_type = invoice and invoice.move_type in (
                'out_invoice', 'in_refund') and 'inbound' or 'outbound'
            payment_methods = payment_type == 'inbound' and Journal.inbound_payment_method_ids or Journal.outbound_payment_method_ids
            payment_method_id = payment_methods and payment_methods[0] or False
            register_payments = self.env['account.payment.register'].with_context({
                'active_model': 'account.move',
                'active_ids': [invoice.id],
            }).create({
                'payment_date': fields.Date.context_today(self),
                'amount': invoice.amount_total,
                'journal_id': Journal.id,
                'payment_method_id': payment_method_id and payment_method_id.id,
            })
            payment = register_payments._create_payments()
            payment.action_post()
        return res

    @api.model
    def _process_order_new(self, order):
        (partner, shipping_partner) = self._process_order_new_find_partners(order)
        fp = self.env['account.fiscal.position'].get_fiscal_position(partner.id, delivery_id=shipping_partner.id)
        if fp:
            partner.property_account_position_id = fp
        create_values = {
            'partner_id': partner.id,
            'partner_shipping_id': shipping_partner.id,
            'state': 'draft',
            'client_order_ref': order['OrderID'],
            'origin': 'eBay' + order['OrderID'],
            'fiscal_position_id': fp.id,
            'is_ebay_order': True,
            'date_order': _ebay_parse_date(order['PaidTime']),
        }
        if self.env['ir.config_parameter'].sudo().get_param('ebay_sales_team'):
            create_values['team_id'] = int(
                self.env['ir.config_parameter'].sudo().get_param('ebay_sales_team'))

        sale_order = self.env['sale.order'].create(create_values)

        for transaction in order['TransactionArray']['Transaction']:
            sale_order._process_order_new_transaction(transaction)

        sale_order._process_order_shipping(order)


SaleOrder()


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model
    def create(self, vals):
        line = super(SaleOrderLine, self).create(vals)
        if len(line.order_id.order_line.filtered(lambda o_line: o_line.product_id.type != 'service').ids) == 1:
            product_id = line.order_id.order_line.mapped('product_id')[0]
            qty = line.order_id.order_line.mapped('product_uom_qty')[0]
            if product_id.is_flat_rate and product_id.delivery_carrier_id == line.order_id.carrier_id and line.name == product_id.delivery_carrier_id.name:
                line.price_unit = product_id.flat_rate * qty
        return line

    def write(self, vals):
        for so_line in self:
            if len(so_line.order_id.order_line.filtered(lambda o_line: o_line.product_id.type != 'service').ids) == 1:
                product_id = so_line.order_id.order_line.mapped('product_id')[0]
                qty = so_line.order_id.order_line.mapped('product_uom_qty')[0]
                if product_id.is_flat_rate and product_id.delivery_carrier_id == so_line.order_id.carrier_id and so_line.name == product_id.delivery_carrier_id.name:
                    vals['price_unit'] = product_id.flat_rate * qty
        line = super(SaleOrderLine, self).write(vals)
        return line
