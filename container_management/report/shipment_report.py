# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime, date
import pytz


class ShipmentReport(models.Model):
    _name = 'shipment.report'

    #    @api.multi
    def po_shipment_records(self, data):
        from_date = data.get('from_date')
        to_date = data.get('to_date') + " 23:59:59"
        po_lines_list = []
        domain = [('date_planned', '>=', from_date), ('date_planned', '<=', to_date),
                  ('state', 'in', ['purchase', 'transit', 'done'])]
        if data.get('partner_id', False):
            domain.extend([('partner_id', '=', data.get('partner_id'))])
        po_lines = self.env['purchase.order.line'].search(domain)
        po_lines = po_lines.sorted(
            key=lambda line: (line.partner_id.display_name, line.order_id.name, line.date_planned))
        for line in po_lines:
            vals = {'purchase_line': line, 'container_lines': []}
            if line.container_line_ids:
                container_lines = line.container_line_ids
                if container_lines:
                    vals.update({'container_lines': container_lines})
            # else:
            #     move_line_ids = line.move_line_ids
            #     if move_line_ids:
            #         move_line_ids = move_line_ids.filtered(lambda rec: rec.state == 'done')
            #         vals.update({'move_line_ids': move_line_ids})
            # not_shipped_ids = line.move_line_ids and line.move_line_ids.filtered(
            #     lambda rec: rec.state not in ['done', 'cancel'])

            # if not_shipped_ids:
            #     vals.update({'shipment_status': 'not_shipped', 'not_shipped_ids': not_shipped_ids})
            if vals.get('move_line_ids', []) or vals.get('not_shipped_ids', []) or vals.get('container_lines', []):
                po_lines_list.append(vals)
        return po_lines_list

    #    @api.multi
    def po_late_shipment_records(self, data):
        po_lines = []
        from_date = data.get('from_date')
        to_date = data.get('to_date') + " 23:59:59"
        domain = [('date_planned', '>=', from_date), ('date_planned', '<=', to_date),
                  ('state', 'in', ['purchase', 'transit', 'done'])]
        if data.get('partner_id', False):
            domain.extend([('partner_id', '=', data.get('partner_id'))])
        po_line_ids = self.env['purchase.order.line'].search(domain)
        po_line_ids = po_line_ids.sorted(
            key=lambda line: (line.partner_id.display_name, line.order_id.name, line.date_planned))
        for line in po_line_ids:
            vals = {'purchase_line': line, 'container_lines': []}
            date_planned = datetime.strftime(line.date_planned, "%Y-%m-%d %H:%M:%S")
            date_planned = datetime.strptime(date_planned, "%Y-%m-%d %H:%M:%S")
            if line.container_line_ids:
                container_lines = line.container_line_ids.filtered(lambda line: line.etd > date_planned)
                if container_lines:
                    vals.update({'container_lines': container_lines})
            # else:
            #     move_line_ids = line.move_line_ids
            #     if move_line_ids:
            #         move_line_ids = move_line_ids.filtered(
            #             lambda rec: datetime.strptime(rec.date_expected, "%Y-%m-%d %H:%M:%S").strftime(
            #                 '%Y-%m-%d') > date_planned and rec.state == 'done')
            #         if move_line_ids:
            #             vals.update({'move_line_ids': move_line_ids})
            # not_shipped_ids = line.move_line_ids and line.move_line_ids.filtered(
            #     lambda rec: rec.state not in ['done', 'cancel'])

            # if not_shipped_ids:
            #     vals.update({'shipment_status': 'not_shipped', 'not_shipped_ids': not_shipped_ids})
            if vals.get('move_line_ids', []) or vals.get('not_shipped_ids', []) or vals.get('container_lines', []):
                po_lines.append(vals)
        return po_lines


ShipmentReport()


class PoShipment(models.AbstractModel):
    _name = 'report.container_management.print_po_shipment_report'

    @api.model
    def _get_report_values(self, docids, data=None):
        report_lines = []
        if data.get('report') == 'shipment':
            report_lines = self.env['shipment.report'].po_shipment_records(data)
            data.update({'heading': 'PO Shipment Report'})
        else:
            report_lines = self.env['shipment.report'].po_late_shipment_records(data)
            data.update({'heading': 'PO Late Shipment Report'})
        return {
            'doc_ids': self._ids,
            'data': data,
            'company_id': self.env.user.company_id,
            'report_lines': report_lines
        }

    # @api.model
    # def render_html(self, docids, data=None):
    #     report_lines = []
    #     if data.get('report') == 'shipment':
    #         report_lines = self.env['shipment.report'].po_shipment_records(data)
    #         data.update({'heading' : 'PO Shipment Report'})
    #     else:
    #         report_lines = self.env['shipment.report'].po_late_shipment_records(data)
    #         data.update({'heading':'PO Late Shipment Report'})
    #     docargs = {
    #         'doc_ids': self._ids,
    #         'data': data,
    #         'company_id' : self.env.user.company_id,
    #         'report_lines' : report_lines
    #     }
    #     return self.env['report'].render('container_management.print_po_shipment_report', docargs)


PoShipment()
