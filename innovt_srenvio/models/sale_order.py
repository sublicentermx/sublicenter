# -*- coding: utf-8 -*-
# Part of Sentilis. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    carrier_delivery_type = fields.Selection(
        related="carrier_id.delivery_type")
    srenvio_provider = fields.Char("Proveedor")
    srenvio_service_level_code = fields.Char("Código de servicio")
    skydropx_total_package = fields.Integer("No. Guía(s)")
    skydropx_packaging_id = fields.Many2one(
        'stock.package.type', string="Tipo de paquete")

    @api.model
    def _skydropx_cal_allowed_lines(self):
        self.ensure_one()
        product_id = self.env.ref(
            'innovt_srenvio.product_product_skydropx_ensure_shipment')
        lines = []
        for line in self.order_line:
            if line.is_delivery or line.product_id.id == product_id.id:
                logger.info("Sale Order: %s Skydropx skip cal product: %s" % (
                    self.name, line.product_id.name))
                continue
            lines.append(line)
        return lines

    @api.model
    def _skydropx_cal_insure_shipment(self):
        self.ensure_one()
        price_list = self.env.ref(
            'innovt_srenvio.product_pricelist_skydropx_ensure_shipment')
        price_insure = 0
        if len(price_list):
            for line in self._skydropx_cal_allowed_lines():
                price, rule = price_list.get_product_price_rule(
                    line.product_id,
                    line.product_uom_qty,
                    self.partner_id
                )
                logger.info("Product: %s - Price: $%s x Qty: %s Rule: %s" %
                            (line.product_id.name, price, line.product_uom_qty, rule))
                price_insure += round(price * line.product_uom_qty, 2)
        logger.info("Sale Order: %s Insure: $%s" % (self.name, price_insure))
        return price_insure

    def _remove_skydropx_insure_line(self):
        product_id = self.env.ref(
            'innovt_srenvio.product_product_skydropx_ensure_shipment')
        if len(product_id):
            self.env['sale.order.line'].search(
                [('order_id', 'in', self.ids), ('product_id', '=', product_id.id)]).unlink()

    @api.model
    def _create_skydropx_insure_line(self, price_unit):
        sequence = False
        if self.order_line:
            sequence = self.order_line[-1].sequence + 1

        product_id = self.env.ref(
            'innovt_srenvio.product_product_skydropx_ensure_shipment')
        if len(product_id):
            # Apply fiscal position
            taxes = product_id.taxes_id.filtered(
                lambda t: t.company_id.id == self.company_id.id)
            taxes_ids = taxes.ids
            if self.partner_id and self.fiscal_position_id:
                taxes_ids = self.fiscal_position_id.map_tax(
                    taxes, product_id, self.partner_id).ids

            values = {
                'order_id': self.id,
                'name': product_id.description_sale or product_id.name,
                'product_uom_qty': 1,
                'product_uom': product_id.uom_id.id,
                'product_id': product_id.id,
                'price_unit': price_unit,
                'tax_id': [(6, 0, taxes_ids)],
                #'is_delivery': True,
                'sequence': sequence
            }
            sol = self.env['sale.order.line'].sudo().create(values)
            return sol
        else:
            logger.error(
                "Not found pruduct: innovt_srenvio.product_product_skydropx_ensure_shipment. Unable to add insurance line skydropx")

    def set_skydropx_insure_line(self):
        self._remove_skydropx_insure_line()

        for order in self:
            if order.state not in ('draft', 'sent'):
                raise UserError(
                    _('Lo puedes agregar el seguro de envío en presupuestos no confirmados.'))
            elif not order.srenvio_provider or not order.srenvio_service_level_code:
                raise UserError(
                    _('No se ha establecido ningún operador para este pedido.'))
            # elif not order.carrier_id.srenvio_enable_insure_shipment: TODO: Any so can added insure shipment
            #    raise UserError(_('El seguro de envio no se puede agregar porque no esta activo en la configuración del Skydropx'))
            else:
                price_list = self.env.ref(
                    'innovt_srenvio.product_pricelist_skydropx_ensure_shipment')
                if len(price_list):
                    price_insure = order._skydropx_cal_insure_shipment()
                    order._create_skydropx_insure_line(price_insure)
                else:
                    logger.error(
                        "Not found price list: innovt_srenvio.product_pricelist_skydropx_ensure_shipment")
                    raise UserError(
                        _('No se ha pudido calcular el seguro de envío.'))

    @api.model
    def set_line_delivery_skydropx_cost(self, cost):
        product_id = self.env.ref(
            'innovt_srenvio.product_product_skydropx_ensure_shipment')
        for line in self.order_line:
            if line.is_delivery and line.product_id.id != product_id.id:
                if hasattr(line, 'purchase_price'):
                    line.purchase_price = cost


class ChooseDeliveryCarrier(models.TransientModel):
    _inherit = 'choose.delivery.carrier'

    def update_price(self):
        # self.ensure_one()
        if self.carrier_id and self.delivery_type == 'srenvio' and \
                self._context.get('skydropx_without_wizard', False) == False:

            view_id = self.env.ref(
                'innovt_srenvio.msb_skydroox_provider_wizard_form').id
            return {
                # 'name': _('Package Details'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'skydropx.provider.wizard',
                'view_id': view_id,
                'views': [(view_id, 'form')],
                'target': 'new',
                'context': {
                    'sale_order_id': self.order_id.id,
                    'carrier_id': self.carrier_id.id,
                    'id': self.id
                }
            }
        return super(ChooseDeliveryCarrier, self).update_price()
