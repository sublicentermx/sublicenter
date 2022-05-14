# -*- coding: utf-8 -*-
# Part of Sentilis. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
import logging
from odoo.exceptions import  ValidationError
from .srenvio_request import SrenvioProvider
import json
_logger = logging.getLogger(__name__)


class ProviderSrenvio(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[('srenvio', "SkydropX")], ondelete={'srenvio': 'set default'})

    srenvio_token = fields.Char(string=_("Token"))
    srenvio_package_dimension_unit = fields.Selection([('CM', 'Centimeters')],
                                                  default='CM',
                                                  string=_('Unidad de dimensión del paquete'))
    srenvio_package_weight_unit = fields.Selection([('KG', 'Kilograms')],
                                               default='KG',
                                               string=_("Unidad de peso del paquete"))
    srenvio_default_packaging_id = fields.Many2one('stock.package.type', 
                                                   string=_("Tipo de paquete"))
    srenvio_provider_allowed = fields.Char(string=_("Paqueterias permitidas"), help=_("provider-service_level_code. ex. ESTAFETA-ESTAFETA_NEXT_DAY,UPS-EXPRESS_SAVER ..."))
    srenvio_margin = fields.Integer(string=_("Margen en la tarifa"), 
        help=_("Este porcentaje se incrementa el precio de envio por cada paqueteria"), default=0)
    
    srenvio_enable_insure_shipment = fields.Boolean(string=_("Seguro de envío"), default=False)
    srenvio_warehouse_id = fields.Many2one('stock.warehouse', string='Almacén sitio web')
    
    skydropx_product_code_consignment_note = fields.Char("Código carta porte")
    skydropx_consignment_note_packaging_code = fields.Char("Código de embalaje", help="1H1, 4B")
    
    def srenvio_product_packaging(self):
        if len(self.srenvio_default_packaging_id):
            pp = self.srenvio_default_packaging_id
        else:
            pp = self.env['stock.package.type'].search([(
                'package_carrier_type', '=', 'srenvio'
            )], order="max_weight asc")
        return pp

    def srenvio_shipping_from(self, order):
        if getattr(order, 'warehouse_id', False) and len(order.warehouse_id):
            partner_id = order.warehouse_id.partner_id
            _logger.info("Skydropx: Shipping address from %s order.warehouse_id.partner_id" % order.warehouse_id.name)
        else: 
            partner_id = order.company_id.partner_id
            _logger.info("Skydropx: Shipping address from order.company_id")

        return partner_id

    def srenvio_rate_shipment(self, order):
        se = SrenvioProvider(self)
        provider = self._context.get('provider', order.srenvio_provider)
        service_level_code = self._context.get('service_level_code', order.srenvio_service_level_code)
        success = False
        price =  False
        error_message = _("Seleecione un proveedor y un nivel de servicio")
        warning_message = False
        if provider and service_level_code:
            quotations = se.srenvio_quotations(order)
            error_message = _("Fallo al generar la cotización, intente de nuevo o cambie de paquetería.")
            if len(quotations):
                error_message = _("El código de nivel de servicio y  proveedor no se encuentra en las cotizacion solicitada, seleccione otro proveedor, por favor.")
                for quotation in quotations: 
                    if quotation['provider'] == provider and quotation['service_level_code'] == service_level_code:
                        price = quotation['skydropx_rate_pricing'] * float(quotation['skydropx_total_package'])
                        success =  True
                        error_message = False
                        order.srenvio_provider = provider
                        order.srenvio_service_level_code = service_level_code
                        order.skydropx_total_package = quotation['skydropx_total_package']
                        break               
        return {'success': success,
                'price': price,
                'error_message': error_message,
                'warning_message': warning_message}
       
    def srenvio_send_shipping(self, pickings):
        se = SrenvioProvider(self)
        res = []
        for picking in pickings:
            order = picking.sale_id
            company_id = order.company_id or picking.company_id or self.env.user.company_id
            skydropx_multi_tracking_ref = []
            multi_pricing = 0.0
            is_sale = len(picking.sale_id) == 1

            if is_sale and not picking.skydropx_provider:
                total_packages = order.skydropx_total_package
                order_currency = picking.sale_id.currency_id 
            else:
                picking.is_skydropx_carrier()
                total_packages = picking.skydropx_total_package
                order_currency = company_id.currency_id
                address_from, address_to = picking.get_skydropx_delivery_address()
                package = se.package_size_calculation(picking.get_skydropx_estimate_weight())
                content = picking.get_skydropx_content()

            for no_package in range(total_packages):
                try:
                    consignment_note = picking.skydropx_product_code_consignment_note or self.skydropx_product_code_consignment_note or ""
                    consignment_note_packaging_code = picking.skydropx_consignment_note_packaging_code or self.skydropx_consignment_note_packaging_code or ""
                    if is_sale and not picking.skydropx_provider:
                        shipping = se.srenvio_shipments(order, consignment_note, consignment_note_packaging_code)
                    else:
                        shipping = se.shipments(
                            address_from, address_to,package,content,
                            picking.skydropx_provider, 
                            picking.skydropx_service_level_code,
                            consignment_note,
                            consignment_note_packaging_code
                        )
                    
                    total_pricing = float(shipping['attributes']['total_pricing'])
                    currency_local = shipping['attributes']['currency_local']
                    if order_currency.name == currency_local:
                        multi_pricing += total_pricing
                    else:
                        quote_currency = self.env['res.currency'].search([('name', '=',currency_local )], limit=1)
                        multi_pricing += quote_currency._convert(total_pricing, order_currency, company_id, order.date_order or fields.Date.today())

                    shipping_id = int(shipping['shipping_id'])
                    label_id = int(shipping['id'])

                    label = se.srenvio_label(label_id)
                    tracking_number = label['attributes']['tracking_number']
                    tracking_url_provider =  label['attributes']['tracking_url_provider']
                    label_url = label['attributes']['label_url']

                    logmessage = """
                    Guía No. {} Generada en Skydropx <br/>
                    <ul class="o_mail_thread_message_tracking">
                        <li>$ {} {}</li>
                        <li>Código de rastreo: <span>{}</span></li>
                        <li><a href='{}' target='_blank'>Seguimiento de envío</a></li>
                        <li><a href='{}' target='_blank'>Descargar Guia</a></li>
                    </ul>""".format(
                        no_package + 1, 
                        total_pricing,  currency_local,  
                        tracking_number,
                        tracking_url_provider,
                        label_url,
                    )
                    skydropx_multi_tracking_ref.append({
                        'tracking_number': tracking_number, 
                        'tracking_url_provider':  tracking_url_provider,
                        'shipping_id':shipping_id, 
                        'label_id': label_id,
                    })
                    picking.message_post(body=logmessage)
                except Exception as e:
                    picking.message_post(body=str(e))
                    raise ValidationError(str(e))

            picking.skydropx_multi_tracking_ref = json.dumps(skydropx_multi_tracking_ref)
            shipping_data = {
                'exact_price': multi_pricing,
                'tracking_number': ','.join([ l.get('tracking_number')  for l in skydropx_multi_tracking_ref])
            }


            if is_sale:
                order.set_line_delivery_skydropx_cost(multi_pricing/1.16)

            res = res + [shipping_data]
        return res

    def srenvio_get_tracking_link(self, picking):
        try:
            links = [ [l.get('tracking_number'), l.get('tracking_url_provider')]  for l in json.loads(picking.skydropx_multi_tracking_ref) ]
            if len(links)>1:
                return json.dumps(links)
            elif len(links) == 1: 
                return links[0][1]
        except Exception as e:
            pass        
        return  False

    def srenvio_cancel_shipment(self, picking):
        for tracking_ref in  str(picking.carrier_tracking_ref).split(','):
            ref = tracking_ref.strip()
            #try:
            reason =  _("Cliente cancelo la compra.")
            se = SrenvioProvider(self)
            clabel = se.cancel_label(ref, reason)
            reason += "<br/> Código de rastreo: " +ref + " <br/> Estatus: " + clabel.get('attributes',{}).get('status', "")
            picking.message_post(body=reason)
            #except Exception as e:
            #    picking.message_post(body= ref+" - " + str(e))
            
        
    