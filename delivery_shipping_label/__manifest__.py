{
    'name': 'Delivery Shipping Label',
    'category': 'inventory',
    'summary': '',
    'summary': 'Delivery changes, product packaging changes etc',
    'version': '1.0',
    'description': """
Delivery Enhancements
======================


This Module provides the changes in inventory related operations.

        """,
    'author': 'Confianz Global',
    'depends': ['stock', 'stock_picking_batch'],
    'demo': [],
    'data': [
        'reports/packing_slip_template.xml',
        'reports/delivery_report.xml',
        'views/stock_picking.xml',
        'views/product_view.xml'

    ],
    'qweb': [],
    'installable': True,
}
