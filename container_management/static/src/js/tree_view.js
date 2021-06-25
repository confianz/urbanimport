odoo.define('tree_view_header.list', function (require) {
    "use strict";

    $(document).ready(function () {
        $(document).ajaxComplete(function () {
            if ($('div.o_view_manager_content div:first-child').hasClass('o_list_editable') == false) {
                var hash = window.location.hash.substr(1).split('&');
                if (jQuery.inArray("view_type=list", hash) != -1 && $("table").length) {

                    var td_class = []
                    $('tbody:first tr:first-child').children().each(function () {
                        if ($(this).hasClass('o_list_number')) {
                            td_class.push('o_list_number');
                        } else {
                            td_class.push('');
                        }
                    });
                    console.log(td_class);
                    td_class.reverse();
                    $('thead tr th').each(function () {
                        $(this).addClass(td_class.pop());
                    });
                }
            }

        });
    });

});
