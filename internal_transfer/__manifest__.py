# -*- coding: utf-8 -*-

{
    "name": "Internal Transfer ",
    "version": "1.1",
    "category": 'Inventory Management',
    'complexity': "normal",
    'author': 'Confianz Global,Inc.',
    'website': 'http://www.confianzit.com',

    "depends": ['sale','stock','delivery','purchase_stock'],

    'data': [
            "security/ir.model.access.csv",
            "data/internal_transer_seq_data.xml",
            "views/internal_transfer_view.xml",
            "views/internal_transfer_exception_view.xml",
            "views/stock_warehouse_view.xml",
            "views/res_partner_view.xml",
    ],
    'demo_xml': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
