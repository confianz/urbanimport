from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    containers_count = fields.Integer(string="# Containers", compute = 'compute_containers')

    def compute_containers(self):
        for pdct in self:
            containers = self.env['container.line'].search([('purchase_line.product_id.product_tmpl_id', '=', pdct.id)]).mapped('container_id')
            pdct.containers_count = len(containers)

    def view_container_lines(self):
        action = self.env.ref('container_management.action_view_container_lines_2')
        containers = self.env['container.line'].search([('purchase_line.product_id.product_tmpl_id', '=', self.id)]).ids
        result = action.read()[0]
        result['context'] = {
                            }
        if len(containers) > 0:
            result['domain'] = "[('id', 'in', " + str(containers) + ")]"
        return result
