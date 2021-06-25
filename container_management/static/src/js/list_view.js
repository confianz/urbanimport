odoo.define('container_management.tree', function (require) {
    "use strict";

    $(document).ready(function () {
        $(document).ajaxComplete(function () {
            var hash = window.location.hash.substr(1).split('&');
            if (jQuery.inArray("view_type=list", hash) != -1 && jQuery.inArray("model=container.container", hash) != -1 && $("table").length) {
                $('thead tr th:last').html('Is Priority');
            }
        });
    });

});
