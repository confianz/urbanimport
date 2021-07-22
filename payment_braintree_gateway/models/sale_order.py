from odoo import api, fields, models, tools, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def create_and_open_payment_sale(self):
        self.ensure_one()
        payment_link_wiz = self.env['payment.link.wizard'].create({
            'res_model': "sale.order",
            'res_id': self.id,
            'amount': self.amount_total,
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
        for record in self:
            for invoice in record.invoice_ids.filtered(lambda l: l.state != 'cancelled'):
                invoice.button_cancel()
        res = super(SaleOrder, self).action_cancel()
        return res
