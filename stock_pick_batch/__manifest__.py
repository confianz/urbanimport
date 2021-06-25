# -*- coding: utf-8 -*-

{
    "name": "Stock Picking Batch",
    "version": "1.1",
    "category": 'Inventory',
    'complexity': "normal",
    'author': 'Confianz Global,Inc.',
    'description': """
Batch transfer in inventory
    """,
    'website': 'http://www.confianzit.com',

    "depends": ['base','stock_picking_batch','stock','delivery'],

    'data': [
            'views/stock_view.xml',
            'report/batch_picking_report.xml',
            'report/batch_picking_report_views.xml',
            'static/src/xml/batch_transfer_ruvati.xml'

    ],
    'demo_xml': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
