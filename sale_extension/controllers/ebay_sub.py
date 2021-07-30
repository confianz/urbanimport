from odoo import fields, http, tools, _
from odoo.http import request
import json
import werkzeug.wrappers
import logging
import hashlib

_logger = logging.getLogger(__name__)


class MyController(http.Controller):

    @http.route('/ebay/notification', type='http', auth="public", methods=['GET', 'POST'], csrf=False)
    def save_rate(self, **kwargs):
        logging.error("kwargs----------------- %s" % str(kwargs))
        params = request.httprequest.get_data()
        logging.error("params----------------- %s" % str(params))
        # kwargs = kwargs.decode('UTF-8')
        # logging.error("params----------------- %s" % str(params))
        # kwargs = json.loads(kwargs)
        # logging.error("params----------------- %s" % str(params))
        m = ''
        if 'challenge_code' in kwargs:
            challenge_code = kwargs['challenge_code']
            endpointurl = 'https://staging-urbanimport.odoo.com/ebay/notification'
            verificationToken = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
            m = hashlib.sha256((challenge_code + verificationToken + endpointurl).encode('utf-8'))
            logging.error("m----------------- %s" % str(m))
            logging.error("m.hexdigest()----------------- %s" % str(m.hexdigest()))
        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps(
                {
                    "challengeResponse": m.hexdigest()
                }
            ),
        )


    # @http.route('/ebay/notification', type='json', auth="public", methods=['GET', 'POST'], csrf=False)
    # def save_rate(self, **kwargs):
    #     logging.error("kwargs----------------- %s" % str(kwargs))
    #     params = request.httprequest.get_data()
    #     logging.error("params----------------- %s" % str(params))
    #     #kwargs = kwargs.decode('UTF-8')
    #     #logging.error("params----------------- %s" % str(params))
    #     #kwargs = json.loads(kwargs)
    #     #logging.error("params----------------- %s" % str(params))
    #     m = ''
    #     if 'challenge_code' in kwargs:
    #         challenge_code = kwargs['challenge_code']
    #         endpointurl = 'https://staging-urbanimport.odoo.com/ebay/notification'
    #         verificationToken = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    #         m = hashlib.sha256((challenge_code + verificationToken + endpointurl).encode('utf-8'));
    #         logging.error("m----------------- %s" % str(m))
    #         logging.error("m.hexdigest()----------------- %s" % str(m.hexdigest()))
    #     return werkzeug.wrappers.Response(
    #         status=200,
    #         content_type="application/json; charset=utf-8",
    #         headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
    #         response={}
    #     )
