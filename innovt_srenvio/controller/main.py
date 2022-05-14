# -*- coding: utf-8 -*-
# Part of Sentilis. See LICENSE file for full copyright and licensing details.

from odoo import http, _
from odoo.http import request
from odoo.addons.website_sale_delivery.controllers.main import WebsiteSaleDelivery
from odoo.addons.website_sale.controllers.main import WebsiteSale, PaymentPortal

from odoo.addons.innovt_srenvio.models.srenvio_request import SrenvioProvider
import logging
import pprint
import werkzeug
import requests

_logger = logging.getLogger(__name__)

class WebsiteSaleSrenvioDelivery(WebsiteSaleDelivery):
    
    
    @http.route(['/shop/srenvio/shipments'], type='json', auth='public', methods=['POST'], website=True, csrf=False)
    def shop_srenvio_shipments(self, **post):
        order = request.website.sale_get_order()
        carrier_id = int(post['carrier_id'])
        #currency = order.currency_id
        carrier = request.env['delivery.carrier'].sudo().browse(carrier_id)
        if carrier.delivery_type == 'srenvio':
            se = SrenvioProvider(carrier)
            if carrier.srenvio_warehouse_id.user_has_groups("stock.group_stock_multi_warehouses")\
                 and len(carrier.srenvio_warehouse_id):
                 if getattr(order, 'warehouse_id', False):
                    _logger.info("Default warehouse: %s" % order.warehouse_id.name)
                    _logger.info("New warehouse: %s" % carrier.srenvio_warehouse_id.name)
                    order.warehouse_id = carrier.srenvio_warehouse_id
            qoutations = se.srenvio_quotations(order)
        else:
            qoutations = []
        return {
            'status': len(qoutations)>1,
            'qoutations': qoutations,
            'carrier_id': carrier_id,
            'margin': carrier.srenvio_margin
        }

    @http.route(['/shop/update_carrier'], type='json', auth='public', methods=['POST'], website=True, csrf=False)
    def update_eshop_carrier(self, **post):
        print(post)
        carrier_id = int(post['carrier_id'])
        carrier = request.env['delivery.carrier'].sudo().browse(carrier_id)
        order = request.website.sale_get_order()
        if carrier.delivery_type == 'srenvio':
            currency = order.currency_id
            provider = post.get('provider', False)
            service_level_code = post.get('service_level_code', False)
            if provider and service_level_code:
                order.with_context(provider=provider,
                                  service_level_code=service_level_code
                                  )._check_carrier_quotation(force_carrier_id=carrier_id)
                return self._update_website_sale_delivery_return(order, **post)

        else:
            order.srenvio_provider = False
            order.srenvio_service_level_code = False
            order.skydropx_total_package = 0

        return WebsiteSaleDelivery.update_eshop_carrier(self, **post)

    @http.route(['/shop/skydropx/ensure-shipment'], type='json', auth="public", methods=['POST'], website=True)
    def skydropx_ensure_shipment(self, **kw):
        order = request.website.sale_get_order(force_create=True)
        response = {
            'status': False, 
            'message': 'Fail add skydropx ensure shipment. Not found order',
            'price':  0
        }
        if len(order):
            response.update({'status': True})
            ensure_shipment = kw.get('ensure_shipment')
            sale_order_add = kw.get('sale_order_add')

            product_id = request.env.ref('innovt_srenvio.product_product_skydropx_ensure_shipment').sudo()
            price_include_tax = order.env['ir.config_parameter'].sudo().get_param('account.show_line_subtotals_tax_selection', 'tax_excluded')
            if len(product_id):
                if ensure_shipment: 
                    price_list = request.env.ref('innovt_srenvio.product_pricelist_skydropx_ensure_shipment')                
                    if len(price_list):
                        price_ensure_shipment = order._skydropx_cal_insure_shipment()
                        if price_include_tax == 'tax_included' and len(product_id.taxes_id):
                            taxes = product_id.taxes_id.compute_all(
                                price_ensure_shipment, 
                                order.currency_id, 
                                1, 
                                product=product_id, 
                                partner=order.partner_shipping_id
                            )
                            price_ensure_shipment  = round(taxes.get('total_included') or \
                                taxes.get('total_excluded') or price_ensure_shipment, 2)
                        response.update({
                            'message': 'is successfully calculated',
                            'price': price_ensure_shipment
                        })
                        request.session['skydropx_price_ensure_shipment'] = price_ensure_shipment
                        print("Price ensure shipment: ", price_ensure_shipment)
                        if sale_order_add:
                            try:
                                order.set_skydropx_insure_line()
                            except Exception as e:
                                _logger.error(e)
                    else:
                        response.update({
                        'status': False,
                        'message': 'Not found product pricelist with id: innovt_srenvio.product_pricelist_skydropx_ensure_shipment'
                    })
                else:
                    if sale_order_add:
                        order_line_dict = order._cart_update(
                            product_id= product_id.id,
                            set_qty=0
                        )
                    request.session['skydropx_price_ensure_shipment'] = 0
                    response.update({
                        'status': True,
                        'message': 'Shipping insurance line was successfully removed'
                    })
            else:
                response.update({
                    'status': False,
                    'message': 'Not found product with id: innovt_srenvio.product_product_skydropx_ensure_shipment'
                })
        #return werkzeug.utils.redirect("/shop/payment") # 
        return response


class PaymentPortalInherit(PaymentPortal):
    @http.route()
    def shop_payment_transaction(self, order_id, access_token, **kwargs):
        if order_id:
            env = request.env['sale.order']
            domain = [('id', '=', order_id)]
            if access_token:
                env = env.sudo()
                domain.append(('access_token', '=', access_token))
            order = env.search(domain, limit=1)
        else:
            order = request.website.sale_get_order()

        if len(order) and order.carrier_delivery_type =='srenvio':
            price = request.session.get('skydropx_price_ensure_shipment',0)
            if price:           
                try:
                    order.set_skydropx_insure_line()
                except Exception as e:
                    _logger.error(e)
                
        return super(PaymentPortalInherit, self).shop_payment_transaction(order_id, access_token,**kwargs)


class WebsiteSaleInherit(WebsiteSale):        
    @http.route()
    def shop_payment_confirmation(self, **post):
        try: 
            del request.session['skydropx_price_ensure_shipment']
        except Exception as e:
            pass
        return super(WebsiteSaleInherit, self).shop_payment_confirmation(**post)