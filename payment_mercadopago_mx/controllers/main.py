# -*- coding: utf-8 -*-

try:
    import simplejson as json
except ImportError:
    import json
import logging
import pprint

from urllib.request import urlopen

try:
    #python2
    import urlparse as parse
except ImportError:
    #python3
    from urllib import parse

import werkzeug

from odoo import http, SUPERUSER_ID
from odoo.http import request

_logger = logging.getLogger(__name__)

from odoo.addons.payment_mercadopago_mx.mercadopago import mercadopago

class MercadoPagoController(http.Controller):
    _notify_url = '/payment/mercadopago_mx/ipn/'
    _return_url = '/payment/mercadopago_mx/dpn/'
    _cancel_url = '/payment/mercadopago_mx/cancel/'

    def _get_return_url(self, **post):
        """ Extract the return URL from the data coming from MercadoPago. """
#        return_url = post.pop('return_url', '')
#        if not return_url:
#            custom = json.loads(post.pop('custom', False) or '{}')
#            return_url = custom.get('return_url', '/')
        #return_url = '/payment/process'
        return_url = '/payment/status'
        return return_url

    def mercadopago_mx_validate_data(self, **post):
        """ MercadoPago MéxicoIPN: three steps validation to ensure data correctness

         - step 1: return an empty HTTP 200 response -> will be done at the end
           by returning ''
         - step 2: POST the complete, unaltered message back to MercadoPago México(preceded
           by cmd=_notify-validate), with same encoding
         - step 3: mercadopago_mx send either VERIFIED or INVALID (single word)

        Once data is validated, process it. """
        res = False

#       topic = payment
#       id = identificador-de-la-operación
        topic = post.get('topic')
        op_id = post.get('id') or post.get('data.id')

        reference = post.get('external_reference')

        if (not reference and (topic and str(topic) in ["payment"] and op_id) ):
            _logger.info('MercadoPago Méxicotopic:'+str(topic))
            _logger.info('MercadoPago Méxicopayment id to search:'+str(op_id))
            reference = request.env["payment.acquirer"].sudo().mercadopago_mx_get_reference(payment_id=op_id)

        tx = None
        if reference:
            tx = request.env['payment.transaction'].sudo().search( [('reference', '=', reference)])
            _logger.info('mercadopago_mx_validate_data() > payment.transaction founded: %s' % tx.reference)

        _logger.info('MercadoPago: validating data')
        #print "new_post:", new_post
        _logger.info('MercadoPago MéxicoPost: %s' % post)

        if (tx):
            post.update( { 'external_reference': reference } )
            _logger.info('MercadoPago MéxicoPost Updated: %s' % post)
            res = request.env['payment.transaction'].sudo()._handle_feedback_data( 'mercadopago_mx', post)

        return res

    @http.route('/payment/mercadopago_mx/ipn/', type='json', auth='public')
    def mercadopago_mx_ipn(self, **post):
        """ MercadoPago MéxicoIPN. """
        # recibimo algo como http://www.yoursite.com/notifications?topic=payment&id=identificador-de-la-operación
        #segun el topic: # luego se consulta con el "id"
        _logger.info('Beginning MercadoPago MéxicoIPN form_feedback with post data %s', pprint.pformat(post))  # debug
        querys = parse.urlsplit(request.httprequest.url).query
        params = dict(parse.parse_qsl(querys))
        _logger.info(params)
        if (params and ('topic' in params or 'type' in params) and ('id' in params or 'data.id' in params)):
            self.mercadopago_mx_validate_data( **params )
        else:
            self.mercadopago_mx_validate_data(**post)
        return ''

    @http.route('/payment/mercadopago_mx/dpn', type='http', auth="public")
    def mercadopago_mx_dpn(self, **post):
        """ MercadoPago MéxicoDPN """
        _logger.info('Beginning MercadoPago MéxicoDPN form_feedback with post data %s', pprint.pformat(post))  # debug
        return_url = self._get_return_url(**post)
        self.mercadopago_mx_validate_data(**post)
        return werkzeug.utils.redirect(return_url)

    @http.route('/payment/mercadopago_mx/cancel', type='http', auth="public")
    def mercadopago_mx_cancel(self, **post):
        """ When the user cancels its MercadoPago Méxicopayment: GET on this route """
        _logger.info('Beginning MercadoPago Méxicocancel with post data %s', pprint.pformat(post))  # debug
        return_url = self._get_return_url(**post)
        status = post.get('collection_status')
        if status=='null':
            post['collection_status'] = 'cancelled'
        self.mercadopago_mx_validate_data(**post)
        return werkzeug.utils.redirect(return_url)
