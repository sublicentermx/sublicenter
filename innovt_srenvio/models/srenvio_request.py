# -*- coding: utf-8 -*-
# Part of Sentilis. See LICENSE file for full copyright and licensing details.

import werkzeug
import requests
import logging
import pprint
import base64
_logger = logging.getLogger(__name__)
from odoo.exceptions import  ValidationError
from odoo import _

class SrenvioProvider(object):
    
    def __init__(self, carrier):
        if carrier.prod_environment:
            self.url =  "https://api.skydropx.com/v1/"
        else:
            self.url = "https://api-demo.skydropx.com/v1/"
        self.token = carrier.srenvio_token
        self.carrier = carrier
    

    def _srenvio_request_check_errors(self, result):
        if not isinstance(result, dict) :
            result = {}
        if 'errors' in result or \
         'error_message' in result.get('data',{}).get('attributes', {}) or \
          result.get('data',{}).get('attributes', {}).get('status',"") == 'ERROR':
            raise Exception(_("Los datos de la peticion son incrrectos"))
            
    def _srenvio_request(self, url, data, **kwargs):

        headers = {
            'Authorization': 'Token token=%s' % self.token
        }
        method = kwargs.get('method', 'POST')
        _logger.info('Beginning SrEnvio request %s ', url)
        _logger.info('Data SrEnvio request %s ', data)        
        if method == 'POST':
            response = requests.post(url, json=data, headers=headers)        
        status = response.status_code
        try:
            result = response.json()
            _logger.info('Response %s %s', status, pprint.pformat(result))
            self._srenvio_request_check_errors(result)
            return True, result
        except Exception as e :            
            _logger.error('Exception msg: %s ', e)
            _logger.error('Response text: %s %s', status, pprint.pformat(response.text))
            msg  = _("Estatus: %s Msg: Fallo la petición intente de nuevo por favor." % status)
            if 600 > status < 500:
                msg =  response.text
            return False, msg
    
    def srenvio_quotations(self, order):
        shipping = order.partner_shipping_id
        company = self.carrier.srenvio_shipping_from(order)
        package = self.srenvio_cal_package(order)
        return self.quotations(
            company.zip, #  zip_from 
            shipping.zip, #  zip_to
            package, #  package
            order.currency_id,
            order.partner_shipping_id,
        )
        
      
    def srenvio_shipments(self, order, consignment_note, consignment_note_packaging_code):
        content = ""        
        for order_line in order.order_line:
            content += order_line.name
            break
        return self.shipments(
            self.carrier.srenvio_shipping_from(order),
            order.partner_shipping_id, 
            self.srenvio_cal_package(order), 
            content,
            order.srenvio_provider, 
            order.srenvio_service_level_code,
            consignment_note,
            consignment_note_packaging_code
        )
    
    def srenvio_label(self, rate_id):
        url = werkzeug.urls.url_join(self.url, "labels")
        data = {
            "rate_id": rate_id,
            "label_format": "pdf"
        }
        ok, label = self._srenvio_request(url, data)
        if ok:
            label = label['data']
            # TODO - Where is  attached  does fail to open file. 
            #url = label['attributes']['label_url']
            #response = requests.get(url)
            #if response.status_code == 200:
            #    label_base64 = base64.b64encode(response.content)
            #else:
            label_base64 = None
            label['attributes'].update({ 'label_base64': label_base64})
            return label
        
        raise ValidationError(_("Fallo al generar la Guia, intente de nuevo por favor. \n %s" % label))
        
    def cancel_label(self, tracking_number, reason):
        url = werkzeug.urls.url_join(self.url, "cancel_label_requests")
        data = {
            "tracking_number": tracking_number,
            "reason": reason
        }
        ok, cancel_label = self._srenvio_request(url, data)
        if ok: 
            return cancel_label['data']
        raise ValidationError(_("Fallo al cancelar la guia, intente de nuevo por favor. \n %s" % cancel_label))
    
    def srenvio_cal_package(self, order):
        est_weight_value = sum([(line.product_id.weight * line.product_uom_qty) for line in order._skydropx_cal_allowed_lines()]) or 0.0
        package = self.package_size_calculation(est_weight_value)
        order.skydropx_packaging_id =  package.get('product_packaging_id')

        return package
        
    def _srenvio_convert_weight(self, weight, unit='KG'):
        if unit == 'KG':
            return weight
        else:
            raise ValueError
        
    # Lib skydropx v2

    def quotations(self, zip_from: int, zip_to: int, package: dict, currency_id, partner_id):
        """
            currency_id, res.currecny: Is used for cal tax delivery
            partner_id, res.partner: is auxiliar for cal tax
        """
        url = werkzeug.urls.url_join(self.url, "quotations")
        data = {
            "zip_to": zip_to,
            "zip_from": zip_from,
            "parcel": {
                "weight": package.get('weight'),
                "height": package.get('package_height'),
                "width": package.get('package_width'),
                "length": package.get('package_length'),
            }
        }
        ok, quotations = self._srenvio_request(url, data)
        if ok:
            providers_list = []
            if self.carrier.srenvio_provider_allowed:
                providers = str(self.carrier.srenvio_provider_allowed).split(",")
                providers_list = [ str(i).strip() for i in providers]
            quotation_list = []
            if len(providers_list):
                for quotation in quotations:
                    provider_service_level_code = quotation.get("provider", "")+"-"+quotation.get("service_level_code", "")
                    if provider_service_level_code in providers_list:
                        quotation_list.append(quotation)
            else:
                quotation_list  = quotations


            #  tax_excluded, tax_included
            price_include_tax = self.carrier.env['ir.config_parameter'].sudo().get_param('account.show_line_subtotals_tax_selection', 'tax_excluded')
            product_id = self.carrier.env.ref("innovt_srenvio.product_product_delivery_srenvio_natio")
            ## Add skydropx rate
            new_quotation_list = []
            for q in quotation_list:
                margin = self.carrier.srenvio_margin
                total_pricing = float(q['total_pricing'])
                if abs(margin) != 0:
                    skydropx_rate_pricing_untaxed =  round(total_pricing + ( total_pricing * float(margin) / 100), 2)
                else:
                    skydropx_rate_pricing_untaxed = round(total_pricing, 2)

                if price_include_tax == 'tax_included' and len(product_id): 
                    taxes = product_id.taxes_id.compute_all(
                            skydropx_rate_pricing_untaxed, 
                            currency_id, 
                            1, 
                            product=product_id, 
                            partner=partner_id
                        )
                    
                    skydropx_rate_pricing_tax = round(taxes.get('total_included') or \
                        taxes.get('total_excluded') or skydropx_rate_pricing_untaxed, 2)
                else:
                    skydropx_rate_pricing_tax = skydropx_rate_pricing_untaxed
                q.update({
                    'skydropx_rate':margin,
                    'skydropx_rate_pricing':  skydropx_rate_pricing_untaxed, 
                    'skydropx_rate_pricing_tax':  skydropx_rate_pricing_tax,
                    'skydropx_total_package': package.get('total_package')
                })
                new_quotation_list.append(q)
            
            if len(new_quotation_list):
                quotation_list = new_quotation_list

            return quotation_list
        return []

    def package_size_calculation(self, est_weight: float):

        weight = self._srenvio_convert_weight(
            est_weight, 
            self.carrier.srenvio_package_weight_unit
        )
        product_packaging = None
        last_product_packaging = None
        for packaging in self.carrier.srenvio_product_packaging():
            last_product_packaging = packaging            
            max_weight = self._srenvio_convert_weight(
                packaging.max_weight, 
                self.carrier.srenvio_package_weight_unit
            )
            if weight < max_weight:
                if not product_packaging:
                    product_packaging = packaging
                    break
                product_packaging = packaging
        if not last_product_packaging:
            raise Exception("Product packaging not found for skydropx")
        if not product_packaging:
            product_packaging =  last_product_packaging
        
        _logger.info("Skydropx package used: %s " % product_packaging.name)
        max_weight = self._srenvio_convert_weight(
                product_packaging.max_weight, 
                self.carrier.srenvio_package_weight_unit
            )
        package  = {
                'package_width': product_packaging.width,
                'package_length': product_packaging.packaging_length,
                'package_height': product_packaging.height,
                'product_packaging_id': product_packaging,
            }

        if max_weight and weight > max_weight:
            total_package = int(weight / max_weight)
            last_package_weight = weight % max_weight
            #for sequence in range(1, total_package + 1):
            #    pass
            if last_package_weight:
                total_package = total_package + 1
            package.update({'weight':max_weight,'total_package': total_package })
        else:
            package.update({'weight':weight,'total_package':1 })
        return package
    
    def shipments(self, address_from, address_to, package: dict, content: str,
        provider: str, service_level_code: str, consignment_note:str, consignment_note_packaging_code:str ):

        if provider and service_level_code:
            company = address_from
            shipping = address_to
            contents = content

            shipping_street2 = shipping.street2 or shipping.city  or ""
            company_street2 = company.street2 or company.city  or ""

            # if installed module location MX
            if getattr(shipping,  'l10n_mx_edi_colony', False) and getattr(shipping, 'l10n_mx_edi_locality', False):
                shipping_street2 = "Col. {}, Loc.{}, ".format(shipping.l10n_mx_edi_colony, shipping.l10n_mx_edi_locality)
                
            if getattr(company,  'l10n_mx_edi_colony', False) and getattr(company, 'l10n_mx_edi_locality', False):
                company_street2 = "Col. {} Loc.{}, ".format(company.l10n_mx_edi_colony, company.l10n_mx_edi_locality)
            data =  {
                "address_from": {
                    "province": company.state_id.name or "",
                    "city": company.city or "",
                    "name": company.name or "",
                    "zip": company.zip,
                    # country code 3 chars
                    "country": company.country_id.code,
                    "address1": company.street or  "",
                    "company": company.name or "",
                    "address2": company_street2,
                    "phone": company.phone,
                    "email": company.email
                },
                "parcels": [{
                    "weight": package.get('weight'),
                    "distance_unit": self.carrier.srenvio_package_dimension_unit,
                    "mass_unit": self.carrier.srenvio_package_weight_unit,
                    "height": package.get('package_height'),
                    "width": package.get('package_width'),
                    "length": package.get('package_length')
                    }],
                "address_to": {
                    "province": shipping.state_id.code or "",
                    "city": shipping.city or "",
                    "name": shipping.name,
                    "zip": shipping.zip,
                    # Same case adove
                    "country": shipping.country_id.code,
                    "address1": shipping.street or "",
                    "company": shipping.parent_id.name if shipping.company_type == 'person' and shipping.parent_id else  shipping.name,
                    "address2": shipping_street2,
                    "phone": shipping.phone,
                    "email": shipping.email,
                    "contents": contents
                },
                "consignment_note_class_code": consignment_note,
                "consignment_note_packaging_code": consignment_note_packaging_code
            }
            url = werkzeug.urls.url_join(self.url, "shipments")
            ok, shipments = self._srenvio_request(url, data)
            if ok and shipments.get('data',  False) and shipments.get('included', False):
                shipments_data  = shipments.get('data')
                shipments_included  = shipments.get('included')
                for include in shipments_included:
                    attributes = include.get('attributes', {})
                    if attributes.get('provider', "") == provider and attributes.get("service_level_code","") == service_level_code:
                            return {"shipping_id": shipments_data.get("id"), **include}
                raise ValidationError(_("El Proveedor con el codigo de servicio no fue encontrado en el envio creado."
                                        "Intente de nuevo o cambie de Proveedor."))
            raise ValidationError(_("Fallo al generar el envio, intente de nuevo por favor. \n %s" % shipments))
        raise ValidationError(_("Capture los datos de SrEnvio Proveedor  y Codigo de nivel servicio."))
