# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################
{
  "name"                 :  "Odoo Multichannel EBay Connector",
  "summary"              :  """Configure your Ebay Store with odoo and manage backend operations in Odoo. Ebay Odoo Bridge integrates Ebay with Odoo you can import orders, products, etc from Ebay to Odoo. Ebay Odoo Bridge(EOB)""",
  "category"             :  "Website",
  "version"              :  "4.5.5",
  "sequence"             :  1,
  "author"               :  "Webkul Software Pvt. Ltd.",
  "license"              :  "Other proprietary",
  "website"              :  "https://store.webkul.com/Ebay-Odoo-Bridge-EOB.html",
  "description"          :  """Ebay Odoo Bridge
Odoo Ebay Bridge
E-bay Odoo bridge
E bay odoo
Import products
Import customers
Import orders
Ebay to Odoo
Odoo multi-channel bridge
Multi channel connector
Multi platform connector
Multiple platforms bridge
Connect Amazon with odoo
Amazon bridge
Flipkart Bridge
Magento Odoo Bridge
Odoo magento bridge
Woocommerce odoo bridge
Odoo woocommerce bridge
Ebay odoo bridge
Odoo ebay bridge
Multi channel bridge
Prestashop odoo bridge
Odoo prestahop
Akeneo bridge
Marketplace bridge
Multi marketplace connector
Multiple marketplace platform""",
  "live_test_url"        :  "https://odoo14-demo.webkul.com/web?db=odoo_connector",
  "depends"              :  ['odoo_multi_channel_sale'],
  "data"                 :  [
                             'data/data.xml',
                             'views/business_policies_skeletion_view.xml',
                             'views/eob_config.xml',
                             'views/inherited_search_views.xml',
                             'views/inherits_view.xml',
                             'views/feeds_view.xml',
                             'views/dashboard_view_inherited.xml',
                             'wizard/import_operation.xml',
                             'views/category_mapping_view.xml',
                             'wizard/export_product.xml',
                             'wizard/export_template.xml',
                             'security/ir.model.access.csv',
                            ],
  "qweb"                 :  ['qweb/instance_dashboard.xml'],
  "images"               :  ['static/description/banner.gif'],
  "application"          :  True,
  "installable"          :  True,
  "auto_install"         :  False,
  "price"                :  200,
  "currency"             :  "USD",
  "pre_init_hook"        :  "pre_init_check",
}
