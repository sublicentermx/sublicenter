/*
   Part of Sentilis. See LICENSE file for full copyright and licensing details.
*/
'use strict';

odoo.define('website_sale_srenvio_delivery.checkout', function(require) {

    require('web.dom_ready');
    var ajax = require('web.ajax');

    /* Handle interactive carrier choice + cart update */
    var $pay_button = $('button[name="o_payment_submit_button"]');

    if (!$pay_button.length) {
        return $.Deferred().reject("Skydropx: DOM doesn't contain 'button[name=o_payment_submit_button]' ");;
    }

    /*
        TODO: Update parent  price label  when is changed shipping
     */
    var _onCarrierUpdateAnswer = function(result) {

        var $amount_delivery = $('#order_delivery .monetary_field');
        var $amount_untaxed = $('#order_total_untaxed .monetary_field');
        var $amount_tax = $('#order_total_taxes .monetary_field');
        var $amount_total = $('#order_total .monetary_field');

        var $carrierBadge = $('#delivery_carrier input[name="delivery_type"][value=' + result.carrier_id + '] ~ .o_wsale_delivery_badge_price');

        if (result.status === true) {
            $amount_delivery.html(result.new_amount_delivery);
            $amount_untaxed.html(result.new_amount_untaxed);
            $amount_tax.html(result.new_amount_tax);
            $amount_total.html(result.new_amount_total);

            $pay_button.data('disabled_reasons').carrier_selection = false;
            $pay_button.prop('disabled', _.contains($pay_button.data('disabled_reasons'), true));

            if (result.is_free_delivery) {
                $carrierBadge.text(_t('Free'));
            } else {
                $carrierBadge.html(result.new_amount_delivery);
            }
            $carrierBadge.removeClass('o_wsale_delivery_carrier_error');
            if (skydropxEnableInsureShipment()) {
                $('#skydropx-carrier-ensure').show(2000);
            }
        } else {
            $amount_delivery.html(result.new_amount_delivery);
            $amount_untaxed.html(result.new_amount_untaxed);
            $amount_tax.html(result.new_amount_tax);
            $amount_total.html(result.new_amount_total);
            $carrierBadge.addClass('o_wsale_delivery_carrier_error');
            $carrierBadge.text(result.error_message);

        }
    };


    var _onSrenvioCarrierClick = function(ev) {

        var carrier_id = $("#skydropx-carrier input[name='skydropx-carrier-id']").val();
        var $skydropx_delivery = $("#delivery_" + carrier_id);
        $skydropx_delivery.siblings('.o_wsale_delivery_badge_price').html('<span class="fa fa-spinner fa-spin"/>');

        var $payButton = $('button[name="o_payment_submit_button"]');
        $payButton.prop('disabled', true);
        $payButton.data('disabled_reasons', $payButton.data('disabled_reasons') || {});
        $payButton.data('disabled_reasons').carrier_selection = true;

        var subitem_id = $(ev.currentTarget).val();
        var subitem_id_split = subitem_id.split("-");
        var values = {
            'carrier_id': subitem_id_split[0],
            'provider': subitem_id_split[1],
            'service_level_code': subitem_id_split[2]
        };
        ajax.jsonRpc('/shop/update_carrier', 'call', values).then(
            _onCarrierUpdateAnswer
        );

    };

    /* Render Shipments */

    if (!$("#delivery_carrier input[name='delivery_type']").length) {
        return $.Deferred().reject("Skydropx: DOM doesn't contain '#delivery_carrier input[name='delivery_type']' ");;
    }

    var $carriers = $("#delivery_carrier input[name='delivery_type']");

    var dynamicSort = function(property) {
        var sortOrder = 1;
        if (property[0] === "-") {
            sortOrder = -1;
            property = property.substr(1);
        }
        return function(a, b) {
            /* next line works with strings and numbers, 
             * and you may want to customize it to your needs
             */
            var result = (a[property] < b[property]) ? -1 : (a[property] > b[property]) ? 1 : 0;
            return result * sortOrder;
        }
    }
    var dynamicSortMultiple = function() {
        /*
         * save the arguments object as it will be overwritten
         * note that arguments object is an array-like object
         * consisting of the names of the properties to sort by
         */
        var props = arguments;
        return function(obj1, obj2) {
            var i = 0,
                result = 0,
                numberOfProperties = props.length;
            /* try getting a different result from 0 (equal)
             * as long as we have extra properties to compare
             */
            while (result === 0 && i < numberOfProperties) {
                result = dynamicSort(props[i])(obj1, obj2);
                i++;
            }
            return result;
        }
    }

    var skydropxEnableInsureShipment = function() {
        if ($("#skydropx-carrier input[name='skydropx-enable-insure-shipment']").val() === "True") {
            return true
        }
        return false
    }
    var _onSrenvioShipmentsRender = function(result) {

        $pay_button.prop('disabled', true);
        var qcount = result['qoutations'].length;
        var carrier_id = result['carrier_id'];
        var margin = result['margin'];
        var qoutations = result['qoutations'];
        if (result['status']) {
            qoutations = result['qoutations'].sort(dynamicSortMultiple('days', 'total_pricing'))
        }

        $("#srenvio-list-group-subitem").empty();
        for (var i = 0; i < qcount; i++) {
            var shipment = qoutations[i];
            var shipment_input = carrier_id + '-' + shipment['provider'] + '-' + shipment['service_level_code']
            var shipment_label_for = carrier_id + "-" + i
            var shipment_label = shipment['provider'] + " - " + shipment['service_level_name'] + " - " + shipment['skydropx_total_package'] + " Paquete(s)"
            var pricing = parseFloat(shipment['skydropx_rate_pricing'])
            var pricing_tax = parseFloat(shipment['skydropx_rate_pricing_tax'])
            if (pricing != pricing_tax) {
                pricing = pricing_tax
            }
            $("#srenvio-list-group-subitem").append(
                " <li>" +
                " <input value='" + shipment_input + "' id='" + shipment_input + "' " +
                " type='radio'  name='srenvio_delivery_subtype' " +
                ///"checked="order.carrier_id and order.carrier_id.id == delivery.id and 'checked' or False " +
                " class=' " + (qcount == 1 ? 'hidden' : '') + "' /> " +
                " <label class='label-optional' for='" + shipment_label_for + "'>" + shipment_label + " </label>" +
                " <span class='badge pull-right'>$&nbsp;<span class='oe_currency_value'>" + pricing + "</span></span>" +
                " <span class='badge pull-right'><span class='oe_currency_value'>" + shipment['days'] + "</span> Día(s)</span>" +
                " </li>"
            );
        }
        /* Set event onClik subitems*/
        var $srenvioCarriers = $("#srenvio-list-group-subitem input[name='srenvio_delivery_subtype']");
        $srenvioCarriers.click(_onSrenvioCarrierClick);

        //Skydropx - ensure shipment
        if (qcount && skydropxEnableInsureShipment()) {
            $("#srenvio-list-group-subitem").append(`
                <div id="skydropx-carrier-ensure" style="display: none;">
                    <br/>
                    <input type="checkbox" name="skydropx-ensure-shipment"/>
                    <label class='label-optional' for='skydropx-ensure-shipment'> Agregar seguro de envío</label>
                    <span id='skydropx-ensure-shipment-pricing' class='float-right badge badge-secondary'>
                    </span>
                </div>
            `)
            var $skydropx_ensure_shipment = $("#skydropx-carrier-ensure input[name='skydropx-ensure-shipment']");
            $skydropx_ensure_shipment.click(_onClickSkydropxEnsureShipment)
        }

        //  if before is selected skydropx set selected
        var scps = $("#skydropx-carrier input[name='skydropx-carrier-provider-selected']").val()
        var scsls = $("#skydropx-carrier input[name='skydropx-carrier-service-level-selected']").val()
        if (scps.length > 0 && scsls.length > 0) {
            $('#' + carrier_id + '-' + scps + '-' + scsls).prop('checked', true);
            $('#' + carrier_id + '-' + scps + '-' + scsls).click()
            if (skydropxEnableInsureShipment()) {
                $('#skydropx-carrier-ensure').show(2000)
            }
        }

    };
    var _onSrenvioShipmentsClick = function(ev) {
        var carrier_id = $("#skydropx-carrier input[name='skydropx-carrier-id']").val();
        var $payButton = $('button[name="o_payment_submit_button"]');
        $payButton.prop('disabled', true);
        var values = { 'carrier_id': carrier_id };
        ajax.jsonRpc('/shop/srenvio/shipments', 'call', values).then(_onSrenvioShipmentsRender);
    };

    if (!$("#skydropx-carrier input[name='skydropx-carrier-id']").length) {
        return $.Deferred().reject("Skydropx: DOM doesn't contain '#skydropx-carrier input[name='skydropx-carrier-id']'");;
    }

    /*
        Skydropx - ensure shipment
     */

    function _onClickSkydropxEnsureShipment(event) {

        var is_checked = $(event.target).prop("checked")
        var $pricing = $("#skydropx-ensure-shipment-pricing")

        ajax.jsonRpc('/shop/skydropx/ensure-shipment', 'call', {
            'ensure_shipment': is_checked,
            'sale_order_add': false
        }).then(function(result) {
            if (is_checked) {
                if (result['status']) {
                    $pricing.html(` $&nbsp;<span class="oe_currency_value">` + result['price'] + `</span>`)
                        .hide().fadeIn(600);
                } else {
                    console.error(result)
                }
            } else {
                $pricing.html("").hide().fadeIn(600);
            }
        });
    }
    return {
        _onSrenvioShipmentsClick: _onSrenvioShipmentsClick
    }
});