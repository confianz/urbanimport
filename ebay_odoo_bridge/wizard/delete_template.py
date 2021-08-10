# -*- coding: utf-8 -*-
#################################################################################
#
#    Copyright (c) 2019-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#
#################################################################################
from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)
import urllib.parse
def _unescape(text):
    ##
    # Replaces all encoded characters by urlib with plain utf8 string.
    #
    # @param text source text.
    # @return The plain text.

    try:
        return urllib.parse(text.encode('utf8'))
    except Exception as e:
        return text
ExportOperation = [
	('export','Export'),
	('update','Update'),
	('delete', 'EndListing')
]
class ExportTemplates(models.TransientModel):
	_inherit = "export.templates"


	@api.model
	def delete_ebay_products(self, active_id):
		api_obj = self.env["multi.channel.sale"]._get_api( self.channel_id, 'Trading')
		final_message = ""
		if api_obj.get('status'):
			map_id = self.env['channel.template.mappings'].search([('template_name', '=', active_id), ('channel_id', '=', self.channel_id.id)], limit=1)
			template_id = self.env['product.template'].browse(active_id)
			if map_id:
				call_data = {
					'WarningLevel': 'High',
					'ItemID': str(map_id.store_product_id),
					'EndingReason':str(self.ebay_end_reason)
				}
				try:
					response = api_obj['api'].execute(
						'EndFixedPriceItem', call_data)
					result_dict = response.dict()
					if result_dict['Ack'] in ['Success', 'Warning']:
						map_id.unlink()
						template_id.ebay_product_url = ''
						variant_mappings = self.env['channel.product.mappings'].search([('odoo_template_id','=',active_id)])
						if variant_mappings:
							variant_mappings.unlink()
						final_message = "Product has been ended successfully on ebay and its mappings have been deleted also."
					else:
						final_message = "Error in deleting the listing </br>%s"%result_dict[ 'Errors']['LongMessage']
				except Exception as e:
					_logger.info('-------------Exception in deleting the listing--%r',e)
					final_message = 'Error in deleting the ting the product %s'%str(e.message)
			else:
				final_message = "There is no mapping for the product %s. You can not delete it."%template_id.name
		else:
			final_message = "Error in connection ::%s" % api_obj.get('message')
		return final_message

	def delete_products_on_ebay(self):
		final_message = ""
		for record in self:
			context = dict(self._context or {})
			default_data = self.env["multi.channel.sale"]._get_default_data(self.channel_id)
			active_ids = self._context['active_ids']
			for active_id in active_ids:
				final_message = self.delete_ebay_products(active_id)
		wizard_id = self.env['wizard.message'].create({'text': final_message})
		return {
			'name': _("Summary"),
			'view_mode': 'form',
			'view_id': False,
			'view_type': 'form',
			'res_model': 'wizard.message',
			'res_id': wizard_id.id,
			'type': 'ir.actions.act_window',
			'nodestroy': True,
			'target': 'new',
			'domain': '[]',
		}
	# operation = fields.Selection(
	# 	selection=ExportOperation,
	# 	default='import',
	# 	required=1
	# )
	ebay_end_reason = fields.Selection([
		('LostOrBroken','LostOrBroken'),
		('Incorrect','Incorrect'),
		('NotAvailable','NotAvailable'),
		('OtherListingError','OtherListingError'),
		('SellToHighBidder','SellToHighBidder'),
		('CustomCode','CustomCode'),
		('Sold','Sold')],
		string="Ebay End Reason",
		default="NotAvailable",
		help="Reason for ending the reason of listing on ebay.")
		
class ExportOdooProducts(models.TransientModel):
	_inherit = 'export.products'

	def delete_products_on_ebay(self):
		raise ValidationError('You can not delete variants on ebay!!!')