# -*- coding: utf-8 -*-

import logging
import requests
from requests.auth import HTTPBasicAuth

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ShipstationConnector(models.AbstractModel):
    _name = "shipstation.connector"
    _description = "Shipstation API Connector"

    base_url = "https://ssapi.shipstation.com"

    api_key = fields.Char(string="API Key", required=True, copy=False)
    api_secret = fields.Char(string="API Secret", required=True, copy=False)

    # ---------------------- API REQQUEST ------------------------
    def _send_request(self, endpoint, data={}, method="GET"):
        try:
            request_url = self.base_url + endpoint
            headers = {'Content-Type': 'application/json'}
            api_auth = HTTPBasicAuth(self.api_key, self.api_secret)

            res = requests.request(method, request_url, auth=api_auth, headers=headers, json=data)
        except Exception as e:
            _logger.warning("[SHIPSTATION] %s: %s\n%s" % (endpoint, data, e))
            res = False
        return res

    # -------------------- REQQUEST METHODS -----------------------

    def _import_stores(self):
        res = self._send_request('/stores?showInactive=True')
        data = []
        if res and res.ok:
            data = res.json()
        return data

    def _import_carriers(self):
        data = []
        res = self._send_request('/carriers')
        if res and res.ok:
            data = res.json()
        return data

    def _import_warehouses(self):
        data = []
        res = self._send_request('/warehouses')
        if res and res.ok:
            data = res.json()
        else:
            data.append({'warehouseName': 'Default Warehouse', 'isDefault': True})
        return data

    def _import_services(self, carrier_code):
        data = []
        if carrier_code:
            res = self._send_request('/carriers/listservices?carrierCode=%s' % carrier_code)
            if res and res.ok:
                data = res.json()
        return data

    def _import_packages(self, carrier_code):
        data = []
        if carrier_code:
            res = self._send_request('/carriers/listpackages?carrierCode=%s' % carrier_code)
            if res and res.ok:
                data = res.json()
        return data

    def _get_rates(self, data={}):
        """
        data = {
            'carrierCode': 'fedex',
            'serviceCode': None,
            'packageCode': None,
            'fromPostalCode': '78703',
            'toState': 'DC',
            'toCountry': 'US',
            'toPostalCode': '20500',
            'toCity': 'Washington',
            'weight': {
                'value': 3,
                'units': 'ounces'
            },
            'dimensions': {
                'units': 'inches',
                'length': 7,
                'width': 5,
                'height': 6
            },
            'confirmation': 'delivery',
            'residential': False,
        }
        """
        rates = []
        try:
            res = self._send_request('/shipments/getrates', data, method="POST")
            res.raise_for_status()

            if res is not False:
                rates = res.json()
                if 'ExceptionMessage' in rates:
                    raise ValidationError("%s: %s" % (rates.get('Message', ''), rates.get('ExceptionMessage', '')))
        except requests.HTTPError as e:
            raise ValidationError(_("Error From ShipStation : %s" % e))
        return rates


    def _create_order(self, vals={}):
        data = {}
        res = self._send_request('/orders/createorder', vals, method="POST")
        if res and res.ok:
            data = res.json()
        return data

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
