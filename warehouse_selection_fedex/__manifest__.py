# -*- coding: utf-8 -*-

{
    'name': 'Warehouse_selection_avs',
    'version': '14.0',
    'category': 'Generic Modules/Warehouse Management',
    'summary': "Warehouse Selection",
    'description': """
Warehouse Selection with Address Verification
                              
       """,
    'author': 'Confianz Global,Inc.',
    'website': 'https://www.confianzit.com',
    'images': [],
    'data': [
        'views/sale_order_view.xml',
        'views/res_config_view.xml',
    ],
    'init_xml': [
    ],

    'depends': ['delivery', 'delivery_fedex','stock', 'shipstation_shipping', 'sale_extension'],
    'installable': True,
    'auto_install': False,
    'application': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
