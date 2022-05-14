# -*- coding: utf-8 -*-
#   Part of Sentilis. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.addons.innovt_srenvio.models.srenvio_request import SrenvioProvider
import logging

logger = logging.getLogger(__name__)


class SkydropxProvider(models.TransientModel):
    _name = 'skydropx.provider.wizard'
    _description = 'Skydropx provider wizard'

    @api.model
    def _get_providers(self):
        rows = []
        try:
            so = self.env['sale.order'].browse(
                self._context.get('sale_order_id', 0))
            dc = self.env['delivery.carrier'].browse(
                self._context.get('carrier_id', 0))
            stock_picking_id = self.env['stock.picking'].browse(
                self._context.get('stock_picking_id', 0))

            def append_row(quotations):
                for quotation in quotations:
                    _id = "{}-{}".format(quotation.get('provider'),
                                         quotation.get('service_level_code'))
                    price = quotation.get('skydropx_rate_pricing_tax') if quotation.get('skydropx_rate_pricing') != quotation.get(
                        'skydropx_rate_pricing_tax') else quotation.get('skydropx_rate_pricing')
                    _name = "$ {} x {} paquete(s) - {} Día(s) - {} {} ".format(
                        price,
                        quotation.get('skydropx_total_package'),
                        quotation.get('days'),
                        quotation.get('provider'),
                        quotation.get('service_level_name'),

                    )

                    #logger.info("%s  %s -> %s " % ( _name, quotation.get('total_pricing'), quotation.get('skydropx_rate_pricing')))
                    rows.append((_id, _name))

            if len(so) and len(dc):
                sp = SrenvioProvider(dc)
                quotations = sp.srenvio_quotations(so)
                append_row(quotations)
            elif len(stock_picking_id) and len(dc):
                sp = SrenvioProvider(dc)
                company_id, partner_id = stock_picking_id.get_skydropx_delivery_address()
                package = sp.package_size_calculation(
                    stock_picking_id.get_skydropx_estimate_weight())
                quotations = sp.quotations(
                    company_id.zip,
                    partner_id.zip,
                    package,
                    stock_picking_id.company_id.currency_id,
                    partner_id,
                )
                append_row(quotations)
        except Exception as e:
            logger.error(e)

        return rows

    provider = fields.Selection(_get_providers, string="Proveedor")

    def ok(self):
        self.ensure_one()
        if self.provider:
            _id, _name = str(self.provider).split('-')
            if self._context.get('sale_order_id', 0):
                sale_order_id = self._context.get('sale_order_id', 0)
                if sale_order_id:
                    so = self.env['sale.order'].browse(sale_order_id)
                    so.srenvio_provider = _id
                    so.srenvio_service_level_code = _name
                    cdc = self.env['choose.delivery.carrier'].browse(
                        self._context.get('id', 0))
                    if len(cdc):
                        return cdc.with_context(skydropx_without_wizard=True).update_price()
            # Wizard launched from warehouse
            elif self._context.get('stock_picking_id', 0):
                stock_picking_id = self.env['stock.picking'].browse(
                    self._context.get('stock_picking_id'))
                carrier_id = stock_picking_id.carrier_id
                sp = SrenvioProvider(carrier_id)
                package = sp.package_size_calculation(
                    stock_picking_id.get_skydropx_estimate_weight())

                msg = f"""<ul>
                    <li>{_id} - {_name}</li>
                    <li>Total de paquetes: {package.get('total_package')}</li>
                    <li>Tamaño del paquete: Largo {package.get('package_length')} Ancho {package.get('package_width')} Alto {package.get('package_height')}  {carrier_id.srenvio_package_dimension_unit}</li>
                    <li>Peso máximo por paquete: {package.get('weight')} {carrier_id.srenvio_package_weight_unit}</li>
                </ul>"""
                stock_picking_id.message_post(body=msg)
                stock_picking_id.skydropx_provider = _id
                stock_picking_id.skydropx_service_level_code = _name
                stock_picking_id.skydropx_total_package = package.get(
                    'total_package')
                stock_picking_id.skydropx_product_packaging_id = package.get(
                    'product_packaging_id')
        return True
