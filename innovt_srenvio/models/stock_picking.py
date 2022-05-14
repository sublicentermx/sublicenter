# -*- coding: utf-8 -*-
# Part of Sentilis. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models, _
from odoo.exceptions import  ValidationError

class StockPicking(models.Model):
    _inherit = 'stock.picking'


    skydropx_multi_tracking_ref = fields.Text()
    skydropx_packaging_id = fields.Many2one(
        'stock.package.type',
        string="Tipo de paquete ",
        related="sale_id.skydropx_packaging_id"
    )
    # V2
    skydropx_provider = fields.Char("Proveedor")
    skydropx_service_level_code = fields.Char("Código de servicio")
    skydropx_total_package = fields.Integer("No. Guía(s)")
    skydropx_product_packaging_id = fields.Many2one('stock.package.type', "Tipo de paquete")
    skydropx_product_code_consignment_note = fields.Char("Código carta porte")
    skydropx_consignment_note_packaging_code = fields.Char("Código de embalaje", help="1H1, 4B")

    def button_skydropx(self):
        self.ensure_one()

        #if len(self.sale_id):
        #    raise ValidationError("Los datos del transportista no pueden ser modificados,"
        #                          "porque el documento esta relacionado con una SO")
        if not self.carrier_id or self.carrier_id.delivery_type != 'srenvio':
            raise ValidationError("En información adicional, seleccione el Transportista Skydropx")

        view_id = self.env.ref('innovt_srenvio.msb_skydroox_provider_wizard_form').id
        return {
            #'name': _('Package Details'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'skydropx.provider.wizard',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': {
                'stock_picking_id': self.id,
                'carrier_id': self.carrier_id.id,
                'id': self.id
            }
        }
    
    @api.model
    def get_skydropx_delivery_address(self):
        """
            return: partner_company, partner_customer
        """
        return self.picking_type_id.warehouse_id.partner_id, self.partner_id

    @api.model
    def get_skydropx_estimate_weight(self):
        products = self.move_ids_without_package
        return sum([(line.product_id.weight * line.product_uom_qty) for line in products]) or 0.0
    
    @api.model
    def get_skydropx_content(self):
        products = self.move_ids_without_package
        for line in products:
            return line.product_id.name
        return ""

    def is_skydropx_carrier(self):
        if self.carrier_id.delivery_type == 'srenvio':
            if not self.skydropx_provider or not self.skydropx_service_level_code or\
                not self.skydropx_total_package or not self.skydropx_product_packaging_id:
                raise ValidationError("Seleccione una paqueteria de SkydropX para continuar")
            return True
        return False
