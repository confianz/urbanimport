# -*- coding: utf-8 -*-

{
    'name': 'Braintree Payment Acquirer',
    'category': 'Accounting/Payment',
    'summary': 'Braintree Payment Gateway to accept payment in different currencies',
    'version': '14.0.0.1',
    'description': """Braintree Payment Acquirer""",
    'author': 'Deepesh Gandhi',
    'depends': ['payment','sale','account','base'],
    'external_dependencies': {
        'python': ['braintree'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_view.xml',
        'views/sale_order.xml',
        'views/payment_template.xml',
        'views/payment_views.xml',
        'views/payment_braintree_templates.xml',
        'data/payment_acquire_data.xml'
    ],
    'images': ['static/description/odoo-braintree-gateway.png'],
    'installable': True,
    'application': True,
    'price': 70.00,
    'currency':  'USD',
    'post_init_hook': '_create_missing_journal_braintree',
}
