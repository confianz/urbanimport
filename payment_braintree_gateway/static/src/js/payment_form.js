odoo.define('payment_braintree_gateway.payment_form', function (require) {
"use strict";

var ajax = require('web.ajax');
var core = require('web.core');
var PaymentForm = require('payment.payment_form');
var _t = core._t;


PaymentForm.include({

    //load braintree dropin js
    willStart: function(){
        return this._super.apply(this, arguments).then(function () {
            return ajax.loadJS("https://js.braintreegateway.com/web/dropin/1.25.0/js/dropin.min.js");
        })
    },

    //--------------------------------------------------------------------------
    // Privatedropin
    //--------------------------------------------------------------------------

    /**
     * called when clicking on pay now or add payment event to create token for credit card/debit card.
     *
     * @private
     * @param {Event} ev
     * @param {DOMElement} checkedRadio
     * @param {Boolean} addPmEvent
     */
    _CreateBraintreeNonce: function (ev, $checkedRadio, addPmEvent) {
        var self = this;
        if (ev.type === 'submit') {
            var button = $(ev.target).find('*[type="submit"]')[0]
        } else {
            var button = ev.target;
        }
        this.disableButton(button);
        var acquirerID = this.getAcquirerIdFromRadio($checkedRadio);
        var acquirerForm = this.$('#o_payment_add_token_acq_' + acquirerID);
        var inputsForm = $('input', acquirerForm);
        var formData = self.getFormData(inputsForm);
        if (this.options.partnerId === undefined) {
            console.warn('payment_form: unset partner_id when adding new token; things could go wrong');
        }
        var braintree_instance = self.braintree_instance
        if (braintree_instance) {
            self.displayLoading(acquirerID);
            braintree_instance.requestPaymentMethod(function (err, payload){
            if(err){
                self.enableButton(button);
                self.removeLoading(acquirerID);
                return self.displayError(_t('Server Error'), err);
            }

            _.extend(formData, {"nonce": payload.nonce, "bin": payload.details.bin, "lastFour": payload.details.lastFour});
            self._rpc({
                route: formData.data_set,
                params: formData
            }).then (function (data) {
                if (addPmEvent) {
                    if (formData.return_url) {
                        window.location = formData.return_url;
                    } else {
                        window.location.reload();
                    }
                } else {
                    $checkedRadio.val(data.id);
                    self.el.submit();
                }
            }).guardedCatch(function (error) {
                error.event.preventDefault();
                acquirerForm.removeClass('d-none');
                self.enableButton(button);
                self.removeLoading(acquirerID);
                self.displayError(
                    _t('Server Error'),
                    _t("We are not able to add your payment method at the moment.") +
                        self._parseError(error)
                    );
                });
            });
        }
    },

    _CreateBraintreeDropin: function(clientToken){
        var self = this
        braintree.dropin.create({
            authorization: clientToken,
            container: '#dropin-container',
        }, function (createErr, instance) {
            if (createErr) {
                console.log("Error while creating dropin: ", createErr);
                return;
            }
            self.braintree_instance = instance
        });
        var $checkedRadio = this.$('input[type="radio"]:checked');
        if ($checkedRadio.length === 1 && $checkedRadio.data('provider') === 'braintree') {
            var acquirerID = this.getAcquirerIdFromRadio($checkedRadio);
            this.removeLoading(acquirerID);
        }
    },

    displayLoading: function(acquirerID){
        var msg = _t("Please wait..");
        $('div#o_payment_add_token_acq_' + acquirerID).block({
            'message': '<h6 class="text-white"><img src="/web/static/src/img/spin.png" class="fa-pulse"/>' +
                '<br/>' + msg +
                '</h6>',
            'css': {opacity: 0.9, display: 'flex', height: '100%', "justify-content": 'center', "align-items": 'center'},
            'overlayCSS': {opacity: 0.6}
        });
    },

    removeLoading: function(acquirerID){
        $('div#o_payment_add_token_acq_' + acquirerID).unblock();
    },

    _createBraintreeToken: function(acquirerID){
        var self = this
        this._rpc({
            model: 'payment.acquirer',
            route: '/payment/braintree/get_token',
            params: {
                acquired_id: acquirerID
            }
        }).then(function(result) {
            self._CreateBraintreeDropin(result.braintree_client_token)
        });
    },

    /**
     * @override
     */
    updateNewPaymentDisplayStatus: function(){
        var $checkedRadio = this.$('input[type="radio"]:checked');
        var self = this;
        if ($checkedRadio.length !== 1) {
            return;
        }

        if ($checkedRadio.data('provider') === 'braintree') {
            var acquirerID = this.getAcquirerIdFromRadio($checkedRadio);
            this.$('#o_payment_add_token_acq_' + acquirerID).removeClass('d-none');
            this.$('#o_payment_form_acq_' + acquirerID).removeClass('d-none');
            var acquirerForm = this.$('#o_payment_add_token_acq_' + acquirerID);
            var inputsForm = $('input', acquirerForm);
            var formData = self.getFormData(inputsForm);
            this._createBraintreeToken(acquirerID);
        }
        else {
            // need to check whether we need else portion or not.
            this._super.apply(this, arguments);
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    payEvent: function (ev) {
        ev.preventDefault();
        var $checkedRadio = this.$('input[type="radio"]:checked');
        // first we check that the user has selected a authorize as s2s payment method
        if ($checkedRadio.length === 1 && this.isNewPaymentRadio($checkedRadio) && $checkedRadio.data('provider') === 'braintree') {
            this._CreateBraintreeNonce(ev, $checkedRadio);
        } else {
            this._super.apply(this, arguments);
        }
    },
    /**
     * @override
     */
    addPmEvent: function (ev) {
        ev.stopPropagation();
        ev.preventDefault();
        var $checkedRadio = this.$('input[type="radio"]:checked');
        // first we check that the user has selected a authorize as add payment method
        console.log("**********1111111**************", $checkedRadio.data('provider'));
        if ($checkedRadio.length === 1 && this.isNewPaymentRadio($checkedRadio) && $checkedRadio.data('provider') === 'braintree') {
            self.displayLoading(acquirerID);
        } else {
            this._super.apply(this, arguments);
        }
    },

    radioClickEvent: function (ev) {
        // Odoo was calling this method two times. Fixed it by adding
        // below two lines and then calling entire method by super.
        ev.stopPropagation();
        ev.preventDefault();
        this._super.apply(this, arguments);
        var $checkedRadio = this.$('input[type="radio"]:checked');
        if ($checkedRadio.length === 1 && $checkedRadio.data('provider') === 'braintree') {
            var acquirerID = this.getAcquirerIdFromRadio($checkedRadio);
            this.displayLoading(acquirerID);
        }
    }

});
});
