/*
   Part of Sentilis. See LICENSE file for full copyright and licensing details.
*/
odoo.define('website_sale_skydropx_delivery.checkout', function(require) {
    'use strict';
    var core = require('web.core');
    var publicWidget = require('web.public.widget');

    var _t = core._t;
    var skydropx = require('website_sale_srenvio_delivery.checkout');
    require('website_sale_delivery.checkout');

    publicWidget.registry.websiteSaleDelivery.include({
        /**
         * 
         * @override
         */
        start: function() {
            var parentRes = this._super.apply(this, arguments);
            var self = this;
            var $carriers = $('#delivery_carrier input[name="delivery_type"]');
            _.each($carriers, function(carrierInput, k) {
                var $skydropx = $("#skydropx-carrier input[name='skydropx-carrier-id']");
                if (k == 0 && $skydropx.val() === carrierInput.value) {
                    self._showLoading($(carrierInput));
                    skydropx._onSrenvioShipmentsClick($skydropx);
                }
            });
            return parentRes;
        },
        /**
         * @override
         */
        _onCarrierClick: function(ev) {
            var $radio = $(ev.currentTarget).find('input[type="radio"]');
            var skydropx_id = $("#skydropx-carrier input[name='skydropx-carrier-id']").val();
            var carrier_id = $radio.val()
            if (carrier_id === skydropx_id) {
                this._showLoading($radio);
                $radio.prop("checked", true);
                skydropx._onSrenvioShipmentsClick(ev);
            } else {
                $("#srenvio-list-group-subitem").empty();
                this._super.apply(this, arguments);
            }
        },
        /**
         * Methods natives skydropx delivery
         */
    }); // end publicWidget

});