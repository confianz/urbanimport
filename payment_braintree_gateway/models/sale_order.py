from odoo import api, fields, models, tools, _
from odoo.exceptions import Warning, UserError
import logging

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def create_and_open_payment_sale(self):
        self.ensure_one()
        if self.amount_total <= 0:
            raise UserError(_(
                'The Sale Order amount is Zero'))
        transaction = self.env['payment.transaction']
        trans = transaction.search([
            ('payment_id.state', '!=', 'cancel'),
            ('sale_order_ids', 'in', self.id),
        ])
        deposit_product = int(self.env['ir.config_parameter'].sudo().get_param('sale.default_deposit_product_id'))
        down_payments = self.order_line and self.order_line.filtered(lambda l: l.product_id.id == deposit_product).mapped('price_unit')
        down_payments = down_payments and sum(down_payments) or 0
        if not trans:
            amount_total = self.amount_total - down_payments
        else:
            total_payment = trans.mapped('payment_id').mapped('amount')
            amount_total = self.amount_total - sum(total_payment) - down_payments
        if amount_total == 0:
            raise UserError(_(
                'There is no Pending Payment to do'))
        payment_link_wiz = self.env['payment.link.wizard'].create({
            'res_model': "sale.order",
            'res_id': self.id,
            'amount': amount_total,
            'amount_max': self.amount_total,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            'description': self.name,
        })

        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': payment_link_wiz.link,
        }

    def action_cancel(self):
        transaction = self.env['payment.transaction']
        for record in self:
            if not record.invoice_ids or record.invoice_ids.filtered(lambda l: l.state == 'draft'):
                trans_to_cancel = transaction.search([
                    ('payment_id.state', '!=', 'cancel'),
                    ('sale_order_ids', 'in', record.id),
                ])
                if trans_to_cancel:
                    payments_to_cancel = trans_to_cancel.mapped('payment_id')
                    payments_to_cancel.action_draft()
                    payments_to_cancel.action_cancel()
            if record.invoice_ids:
                logging.error("record.invoice_ids.filtered(lambda l: l.state != 'cancelled')-------------%s" % str(record.invoice_ids.filtered(lambda l: l.state != 'cancelled')))

                record.invoice_ids.filtered(lambda l: l.state != 'cancelled').button_cancel()
        res = super(SaleOrder, self).action_cancel()
        return res
