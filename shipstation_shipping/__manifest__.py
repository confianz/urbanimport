# -*- encoding: utf-8 -*-
##############################################################################
#
#    Confianz IT
#    Copyright (C) 2021   (https://www.confianzit.com)
#
##############################################################################


{
    'name': "ShipStation Shipping",
    'version': '14.0.1.0',
    'category': 'Inventory',
    'sequence': '15',
    'description': "Send shippings through ShipStation and track them online",
    'author': 'Confianz IT',
    'website': 'https://www.confianzit.com',
    'depends': ['delivery', 'website_sale_delivery', 'sale_margin'],
    'data': [
        'security/ir.model.access.csv',

        'data/shipstation_shipping_data.xml',

        'views/shipstation_service_views.xml',
        'views/shipstation_package_views.xml',
        'views/shipstation_carrier_views.xml',
        'views/shipstation_warehouse_views.xml',
        'views/shipstation_store_views.xml',
        'views/shipstation_account_views.xml',

        'views/sale_order_view.xml',
        'views/delivery_carrier.xml',

        'wizard/choose_delivery_carrier_view.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
