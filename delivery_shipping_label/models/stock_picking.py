from odoo import models, _, fields, api
import base64
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from PyPDF2 import PdfFileMerger, PdfFileReader, PdfFileWriter
import io
from odoo.exceptions import UserError, ValidationError
import datetime
import zpl


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    picking_type_id_code = fields.Char('Picking Type Code', related='picking_type_id.sequence_code', readonly=True)
    # is_back_order = fields.Boolean(string="Back Order", compute="_compute_back_order",inverse="_inverse_back_order", store=True, copy=False, readonly=False)

    # @api.depends('sale_id.is_back_order')
    # def _compute_back_order(self):
    #     for rec in self:
    #         rec.is_back_order = rec.sale_id.is_back_order

    # def _inverse_back_order(self):
    #     for rec in self:
    #         rec.sale_id.update({'is_back_order': rec.is_back_order})

    # def action_done(self):
    #     for rec in self:
    #         if rec.picking_type_id == rec.picking_type_id.warehouse_id.pick_type_id:
    #             pack_id = self.env.ref('stock.location_pack_zone')
    #             if pack_id and rec.location_dest_id.id == pack_id.id:
    #                 rec.with_context({'validate': True}).put_in_pack()
    #     return super(StockPicking, self).action_done()

    # def action_assign(self):
    #     res = super(StockPicking, self).action_assign()
    #     for rec in self:
    #         if rec.picking_type_id == rec.picking_type_id.warehouse_id.pick_type_id:
    #             pack_id = self.env.ref('stock.location_pack_zone')
    #             if pack_id and rec.location_dest_id.id == pack_id.id:
    #                 rec.with_context({'assign': True}).put_in_pack()
    #     return res

    # def put_in_pack(self):
    #     self.ensure_one()
    #     if self.state not in ('done', 'cancel'):
    #         picking_move_lines = self.move_line_ids
    #         if (
    #             not self.picking_type_id.show_reserved
    #             and not self.env.context.get('barcode_view')
    #         ):
    #             picking_move_lines = self.move_line_nosuggest_ids
    #
    #         move_line_ids = picking_move_lines.filtered(lambda ml:
    #             float_compare(ml.qty_done, 0.0, precision_rounding=ml.product_uom_id.rounding) > 0
    #             and not ml.result_package_id
    #         )
    #         if not move_line_ids:
    #             move_line_ids = picking_move_lines.filtered(lambda ml: float_compare(ml.product_uom_qty, 0.0,
    #                                  precision_rounding=ml.product_uom_id.rounding) > 0 and float_compare(ml.qty_done, 0.0,
    #                                  precision_rounding=ml.product_uom_id.rounding) == 0)
    #         if move_line_ids:
    #             res = self._pre_put_in_pack_hook(move_line_ids)
    #
    #             res = self._put_in_pack(move_line_ids)
    #             return res
    #         else:
    #             raise UserError(_("Please add 'Done' qantitites to the picking to create a new pack."))

    # def put_in_pack(self):
    #     self.ensure_one()
    #     if self.state not in ('done', 'cancel'):
    #         picking_move_lines = self.move_line_ids
    #         if (
    #                 not self.picking_type_id.show_reserved
    #                 and not self.env.context.get('barcode_view')
    #         ):
    #             picking_move_lines = self.move_line_nosuggest_ids
    #
    #         move_line_ids = picking_move_lines.filtered(lambda ml:
    #                                                     float_compare(ml.qty_done, 0.0,
    #                                                                   precision_rounding=ml.product_uom_id.rounding) > 0
    #                                                     )
    #         if not move_line_ids:
    #             move_line_ids = picking_move_lines.filtered(lambda ml: float_compare(ml.product_uom_qty, 0.0,
    #                                                                                  precision_rounding=ml.product_uom_id.rounding) > 0 and float_compare(
    #                 ml.qty_done, 0.0,
    #                 precision_rounding=ml.product_uom_id.rounding) == 0)
    #         if move_line_ids:
    #             res = self._pre_put_in_pack_hook(move_line_ids)
    #
    #             res = self._put_in_pack(move_line_ids)
    #             return res
    #         else:
    #             if self._context.get('assign',False):
    #                 return {}
    #             # raise UserError(_("Please add 'Done' qantitites to the picking to create a new pack."))

    # def _put_in_pack(self, move_line_ids):
    #     package = False
    #     for pick in self:
    #         move_lines_to_pack = self.env['stock.move.line']
    #         # package = self.env['stock.quant.package'].create({})
    #
    #         precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
    #         if float_is_zero(move_line_ids[0].qty_done, precision_digits=precision_digits):
    #             for line in move_line_ids:
    #                 line.qty_done = line.product_uom_qty
    #
    #         for ml in move_line_ids:
    #             if float_compare(ml.qty_done, ml.product_uom_qty,
    #                              precision_rounding=ml.product_uom_id.rounding) >= 0:
    #                 move_lines_to_pack |= ml
    #             else:
    #                 ml.qty_done = 0
    #                 # quantity_left_todo = float_round(
    #                 #     ml.product_uom_qty - ml.qty_done,
    #                 #     precision_rounding=ml.product_uom_id.rounding,
    #                 #     rounding_method='UP')
    #                 # done_to_keep = ml.qty_done
    #                 # new_move_line = ml.copy(
    #                 #     default={'product_uom_qty': 0, 'qty_done': ml.qty_done})
    #                 # ml.write({'product_uom_qty': quantity_left_todo, 'qty_done': 0.0})
    #                 # new_move_line.write({'product_uom_qty': done_to_keep})
    #                 move_lines_to_pack |= ml
    #         Quant = self.env['stock.quant']
    #
    #         for pack_line in move_lines_to_pack:
    #             pack_line_count = 1
    #             reserved_qty = pack_line.product_uom_qty
    #             for line_range in range(int(pack_line.product_uom_qty)):
    #                 new_pack_line = pack_line
    #                 if pack_line.product_uom_qty > 1 and pack_line_count != reserved_qty:
    #                     pack_line_count += 1
    #                     # if pack_line_count == 1:
    #                     #     Quant._update_reserved_quantity(new_pack_line.product_id, new_pack_line.location_id, -pack_line.product_uom_qty,
    #                     #                                     lot_id=False,
    #                     #                                     package_id=new_pack_line.package_id,
    #                     #                                     owner_id=new_pack_line.owner_id, strict=True)
    #
    #                     new_pack_line = pack_line.copy(
    #                         default={'product_uom_qty': 1, 'qty_done': 0})
    #                     pack_line.product_uom_qty -= 1
    #                     pack_line.qty_done = 0
    #
    #                     Quant._update_reserved_quantity(new_pack_line.product_id, new_pack_line.location_id, 1,
    #                                                         lot_id=False,
    #                                                         package_id=new_pack_line.package_id,
    #                                                         owner_id=new_pack_line.owner_id, strict=True)
    #
    #                     new_pack_line.write({'result_package_id': False, 'package_created': False})
    #                 if not new_pack_line.result_package_id and not new_pack_line.package_created:
    #
    #                     package = self.env['stock.quant.package'].create({
    #                         'shipping_weight': pack_line.product_id.weight,
    #                         'height': pack_line.product_id.height,
    #                         'width': pack_line.product_id.width,
    #                         'length': pack_line.product_id.length
    #                     })
    #                     packaging_id = self.env['product.packaging'].create({
    #                         'name': package.name,
    #                         'height': pack_line.product_id.height,
    #                         'width': pack_line.product_id.width,
    #                         'length': pack_line.product_id.length
    #                     })
    #                     package.packaging_id = packaging_id.id
    #
    #                     package_level = self.env['stock.package_level'].create({
    #                         'package_id': package.id,
    #                         'picking_id': pick.id,
    #                         'location_id': False,
    #                         'location_dest_id': move_line_ids.mapped('location_dest_id').id,
    #                         'move_line_ids': [(6, 0, new_pack_line.id)],
    #                         'company_id': pick.company_id.id,
    #                     })
    #                     new_pack_line.write({
    #                         'result_package_id': package.id,
    #                         'package_created': True
    #                     })
    #             if pack_line.product_uom_qty >= 1 and not self._context.get('validate', False):
    #                 pack_line.write({'qty_done': 0})
    #             #     print("vvvvvvvvvvvvvvvvvvvv")
    #             #     # Quant._update_reserved_quantity(pack_line.product_id, pack_line.location_id, -1,
    #             #     #                                 lot_id=False,
    #             #     #                                 package_id=pack_line.package_id,
    #             #     #                                 owner_id=pack_line.owner_id, strict=True)
    #             # else:
    #             #     pack_line.write({'product_uom_qty': 1, 'qty_done': 1})
    #
    #     # for line in self.move_lines:
    #     #     line._recompute_state()
    #
    #     return package

    def _get_fedex_zpl(self):
        packing_slips = []
        # print('self.package_ids',self.package_ids)
        if not self.package_ids:
            raise UserError("No Packages are selected in the transfer")
        for pack in self.package_ids:

            #Header
            l = zpl.Label(100, 60)
            l.origin(0, 3)
            l.write_text("Packing Slip", char_height=2, char_width=2, line_width=60, justification='C')
            l.endorigin()

            l.origin(4, 7)
            l.write_text("Ship TO: %s" % self.partner_id.street, char_height=2, char_width=2, line_width=60, justification='L')

            l.endorigin()

            l.origin(12, 9.8)
            l.write_text("%s %s" % (self.partner_id.city, self.partner_id.zip), char_height=2, char_width=2, line_width=60, justification='L')

            l.endorigin()

            l.origin(12, 12)
            l.write_text("%s (%s)"%(self.partner_id.state_id.name,self.partner_id.state_id.code), char_height=2, char_width=2, line_width=60, justification='L')

            l.endorigin()

            l.origin(12, 14)
            l.write_text(self.partner_id.country_id.name, char_height=2, char_width=2, line_width=60, justification='L')

            l.endorigin()

            l.origin(40, 7)
            l.write_text("Order#: %s" % self.origin, char_height=2, char_width=2, line_width=60, justification='L')

            l.endorigin()

            l.origin(40, 10)
            l.write_text("Date: %s" % datetime.date.today().strftime('%m/%d/%Y'), char_height=2, char_width=2, line_width=60, justification='L')

            l.endorigin()

            l.origin(40, 12)
            l.write_text("Ship Date: %s" % self.scheduled_date.strftime('%m/%d/%Y'), char_height=2, char_width=2, line_width=60, justification='L')

            l.endorigin()

            #Table header

            l.origin(5, 20)
            l.write_text("SKU", char_height=2, char_width=2, line_width=60, justification='L')

            l.endorigin()

            l.origin(50, 20)
            l.write_text("Qty", char_height=2, char_width=2, line_width=60, justification='L')

            l.endorigin()

            l.origin(4, 19)
            l.draw_box(700, 50, thickness=2, color='B', rounding=0)
            l.endorigin()
            if pack.quant_ids:
                for quant in pack.quant_ids:
                    #Table Body
                    l.origin(5, 25)
                    l.write_text(quant.product_id.default_code, char_height=4, char_width=4, line_width=60, justification='L')

                    l.endorigin()

                    l.origin(50, 25)
                    l.write_text(int(quant.quantity), char_height=4, char_width=4, line_width=60, justification='L')

                    l.endorigin()
            else:
                for move_line in self.move_line_ids:
                    if move_line.result_package_id == pack:
                        # Table Body
                        l.origin(5, 25)
                        l.write_text(move_line.product_id.default_code, char_height=4, char_width=4, line_width=60,
                                     justification='L')

                        l.endorigin()

                        l.origin(50, 25)
                        l.write_text(int(move_line.product_uom_qty), char_height=4, char_width=4, line_width=60, justification='L')

                        l.endorigin()

            l.origin(4, 30)
            l.write_text("Dealer# %s" % (self.sale_id.partner_id.email or self.sale_id.partner_id.name), char_height=2,
                         char_width=2, line_width=60, justification='L')

            l.endorigin()
            l.origin(3, 32)
            l.write_text("--------------------------------------------------------------------------", char_height=1,
                         char_width=1, line_width=60, justification='L')

            l.endorigin()

            l.origin(12, 37)
            l.write_barcode(height=70, barcode_type='C', check_digit='Y')
            l.write_text(self.get_order())
            l.endorigin()

            l.origin(4, 50)
            l.write_text("DO NOT REMOVE OR COVER THIS BARCODE.REQUIRED FOR RETURNS", char_height=2, char_width=2,
                         line_width=60, justification='L')

            l.endorigin()
            l.origin(28, 52)
            l.write_text("PROCESSING", char_height=2, char_width=2, line_width=60, justification='L')

            l.endorigin()
            packing_slips.append(l.dumpZPL())
        return packing_slips

    def generate_shipping_label(self):
        if self.carrier_id.delivery_type == 'fedex':
            packing_slips = self._get_fedex_zpl()
            return_label_ids = self.env['ir.attachment'].search(
                [('res_model', '=', 'stock.picking'), ('res_id', '=', self.id),
                 ('name', 'like', '%s%%' % 'LabelFedex')])
            if not return_label_ids:
                raise UserError("Shipping labels not generated")

            return_labels = [base64.b64decode(return_label_id.datas) for return_label_id in return_label_ids]
            zpl_merged = ''
            # print('packing_slips',packing_slips)
            # print('return_labels',return_labels)
            for label_index in range(0,len(return_labels)):
                zpl_merged += return_labels[label_index].decode() + packing_slips[label_index]
            merged_pdf = base64.encodestring(str.encode(zpl_merged))
            label_name = "Shipping_Label.ZPL"

        else:
            packing_slip = self.env.ref('delivery_shipping_label.action_report_packslip').render_qweb_pdf(self.id)[0]
            return_label = self.env.ref('delivery_shipping_label.action_report_labelslip').render_qweb_pdf(self.id)[0]
            return_labels = [return_label]
            packing_slips = [packing_slip]
            delivery_type = self.carrier_id.delivery_type
            merged_pdf = self.with_context(delivery_type=delivery_type).merge_pdfs(packing_slips, return_labels)
            merged_pdf = base64.encodestring(merged_pdf)
            label_name = "Shipping_Label.pdf"

        attachment_id = self.env['ir.attachment'].create({
            'name': label_name,
            'type': 'binary',
            'datas': merged_pdf,
            'res_model': self._name,
            'res_id': self.id
        })
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': '/web/content/%s?download=true' % attachment_id.id,
        }

    def merge_pdfs(self, packing_slips, return_labels):
        ''' Merge a collection of PDF documents in one
        :param list pdf_data: a list of PDF datastrings
        :return: a unique merged PDF datastring
        '''
        writer = PdfFileWriter()
        for document in packing_slips:
            reader_packing = PdfFileReader(io.BytesIO(document), strict=False)
            reader_label = PdfFileReader(io.BytesIO(return_labels[0]), strict=False)
            for page in range(0, reader_label.getNumPages()):
                page_rec = reader_packing.getPage(page)
                page_label = reader_label.getPage(page)
                if self._context.get('delivery_type') == 'fedex':
                    page_label.cropBox.setLowerRight((321, 120))
                    page_label.cropBox.setUpperRight((321, 610))
                    page_label.cropBox.setLowerLeft((31, 120))
                    page_label.cropBox.setUpperLeft((31, 610))
                    page_label_clockwise = page_label.rotateClockwise(270)
                else:
                    # page_label.scaleTo(6*72, 4*72)
                    page_label_clockwise = page_label
                writer.addPage(page_label_clockwise)
                writer.addPage(page_rec)

        _buffer = io.BytesIO()
        writer.write(_buffer)
        merged_pdf = _buffer.getvalue()
        _buffer.close()
        return merged_pdf
        
    def get_order(self):
        """to get the QC picking name for the packing slip barcode
        """
        cr = self._cr
        cr.execute("select move_dest_id from stock_move_move_rel where move_orig_id = %s" % (self.move_lines[0].id))
        pick_move_ids = [x[0] for x in cr.fetchall()]
        # print('pick_move_ids',pick_move_ids)
        # print('self.move_lines[0].id',self.move_lines[0].id)
        qc_picking = pick_move_ids and self.env['stock.move'].browse(pick_move_ids)[0].picking_id or False
        if self.picking_type_id.warehouse_id.delivery_steps == 'pick_pack_ship' and qc_picking and qc_picking.origin == self.origin and qc_picking.picking_type_id == self.picking_type_id.warehouse_id.pack_type_id:
            return qc_picking.name
        return self.name


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'
        
    def generate_shipping_label(self):
        """Prints the Shipping label-Packing slip report for the batch.
        """
        attachments = []
        attachment_ids = []
#        picking_ids = self.picking_ids.filtered(lambda r: r.state == 'done')
#        if not picking_ids:
#            raise ValidationError("Please validate the picking to print lablel")
        delivery_type = False
        for picking in self.picking_ids:
            delivery_type = picking.carrier_id.delivery_type
            attachments.append(picking.generate_shipping_label())
        for attachment in attachments:
            url = attachment['url'].split('?')
            pick_attachment_id = url[0].split('/')[-1]
            pick_attachment = self.env['ir.attachment'].browse(int(pick_attachment_id))
            attachment_ids.append(pick_attachment)
        zpl_merged = ''
        if delivery_type == 'fedex':
            for attach in attachment_ids:
                zpl_merged += base64.b64decode(attach.datas).decode()
            merged_pdf = base64.encodestring(str.encode(zpl_merged))
            label_name = "Shipping_Label.ZPL"
        else:
            merged_pdf = self.merge_packing_slip(attachment_ids)
            label_name = "Shipping_Label.pdf"
            merged_pdf = base64.encodestring(merged_pdf)
        attachment_id = self.env['ir.attachment'].create({
            'name': label_name,
            'type': 'binary',
            'datas': merged_pdf,
            'res_model': self._name,
            'res_id': self.id
        })
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': '/web/content/%s?download=true' % attachment_id.id,
        }
        
    def merge_packing_slip(self, attachment_ids):
        """ Merges the Shipping label-Packing slip report of all pickings in the batch.
        :param attachment_ids: list of PDF datastrings to merge
        :return: a unique merged PDF datastring
        """
        writer = PdfFileWriter()
        for document in attachment_ids:
            pdf_doc = [document and base64.b64decode(document.datas)]
            reader_attachment = PdfFileReader(io.BytesIO(pdf_doc[0]), strict=False)
            for page in range(0, reader_attachment.getNumPages()):
                page_rec = reader_attachment.getPage(page)
                writer.addPage(page_rec)
        _buffer = io.BytesIO()
        writer.write(_buffer)
        merged_pdf = _buffer.getvalue()
        _buffer.close()
        return merged_pdf

    def action_create_label(self):
        """ Creates shipping label for batch of picking
        """
        picking_ids = self.picking_ids.filtered(lambda r: r.is_create_label)
        if not picking_ids:
            raise ValidationError("Label is created for all pickings.")
        for rec in picking_ids:
            rec.action_create_label()


# class StockMoveLine(models.Model):
#     _inherit = 'stock.move.line'
#
#     package_created = fields.Boolean("Package Exists", copy=False)

