# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Container Management',
    'version': '1.0',
    'category': 'Purchases',
    'author'  : "Confianz Global",
    'summary': "This module is used for tracking containers while ocean freight transfer",
    'description': """ """,
    'website': 'https://www.confianzit.com',
    'depends': ['sale','purchase','internal_transfer','base'],
    'images': ['static/description/icon.png'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/stock_internal_transfer_views.xml',
        'wizard/transfer_container.xml',
        'wizard/shipment_report.xml',
        'wizard/container_wizard.xml',
        'views/res_partner.xml',
        'views/house_bill_of_lading.xml',
        'views/container.xml',
        'views/purchase.order.xml',
        'views/stock.xml',
        'views/product_supplier_info.xml',
        'views/product_hts.xml',
        'views/hbl_customs_duty.xml',
        'views/container_config.xml',
        'views/menu.xml',
        'views/account_move.xml',
       'views/product_template_view.xml',
        'views/assets.xml',
        'report/print_po_shipment_report.xml',
        'report/report_paperformat.xml',
    ],
    'demo': [

    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
