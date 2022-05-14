# -*- coding: utf-8 -*-
# Part of Sentilis. See LICENSE file for full copyright and licensing details.

{
    'name': "SkydropX Odoo Connector",

    'summary': "Centralize and control your shipments in one place with skydropx",
    'author': 'Sentilis',
    'category': 'Inventory/Delivery',
    'version': '15.0.1',
    'website': 'https://sentilis.io/odoo/skydropx',
    'live_test_url': 'https://sentilis.io/contact-sales?subject=Skydropx Odoo Connector Demo',
    'support': 'support@sentilis.io',
    'depends': [
        'delivery',
        'mail',
        'website_sale_delivery'
    ],
    'license': 'OPL-1',
    'price': '324.40',
    'currency': 'USD',
    'application':True,
    'data': [
        'security/ir.model.access.csv',

        'data/delivery_srenvio_data.xml',

        'views/sale_order_view.xml',
        'views/delivery_view.xml',
        'views/stock_picking_view.xml',
        'views/website_sale_srenvio_delivery_templates.xml',

        'wizard/skydropx_wizard_view.xml'
    ],
    'assets': {
        'web.assets_frontend': [
            'innovt_srenvio/static/src/js/website_sale_skydropx_delivery.js',
            'innovt_srenvio/static/src/js/website_sale_srenvio_delivery.js',
        ]
    },
    'images': [
        "static/description/cover.png"
    ],
}
