odoo.define('vs_america.ListRenderer', function (require) {
"use strict";
var BasicRenderer = require('web.BasicRenderer');
var config = require('web.config');
var core = require('web.core');
var Dialog = require('web.Dialog');
var dom = require('web.dom');
var field_utils = require('web.field_utils');
var Pager = require('web.Pager');
var utils = require('web.utils');
var ListRender = require('web.ListRenderer');
var _t = core._t;

var FIELD_CLASSES = {
    float: 'o_list_number',
    integer: 'o_list_number',
    monetary: 'o_list_number',
    text: 'o_list_text',
};
    var ListRenderer = require('web.ListRenderer');

    ListRenderer.include({

    _renderHeader: function (isGrouped) {
    if (this.arch.attrs.class!='table_vs_america'){
        var $tr = $('<tr>')
                .append(_.map(this.columns, this._renderHeaderCell.bind(this)));

        if (this.hasSelectors) {
            $tr.prepend(this._renderSelector('th'));
        }
        if (isGrouped) {
            $tr.prepend($('<th>').html('&nbsp;'));
        }

        return $('<thead>').append($tr);
    }
    },



});

});


odoo.define('sale_extensions.basic_fields', function (require) {
"use strict";
/**
 * This module contains most of the basic (meaning: non relational) field
 * widgets. Field widgets are supposed to be used in views inheriting from
 * BasicView, so, they can work with the records obtained from a BasicModel.
 */

var AbstractField = require('web.AbstractField');
var BasicFields = require('web.basic_fields')

//var qweb = core.qweb;
//var _t = core._t;
BasicFields.FieldBinaryFile.include({

    init: function (parent, name, record) {
        this._super.apply(this, arguments);
        this.fields = record.fields;
        this.useFileAPI = !!window.FileReader;
        this.max_upload_size = 100 * 1024 * 1024; // 100Mo
        if (!this.useFileAPI) {
            var self = this;
            this.fileupload_id = _.uniqueId('o_fileupload');
            $(window).on(this.fileupload_id, function () {
                var args = [].slice.call(arguments).slice(1);
                self.on_file_uploaded.apply(self, args);
            });
        }
    },
})

});
odoo.define('vs_america.FormController', function (require) {
"use strict";

var FormController =  require('web.FormController');

FormController.include({
   _onOpenOne2ManyRecord: function (event) {
        if (this.mode === 'readonly') {
                this.reload();
                }
        this._super.apply(this, arguments);
        }
    });
});
odoo.define('vs_america.WebDom', function (require) {
"use strict";

var dom = require('web.dom');

dom.setSelectionRange=function (node, range) {
        if(node.type === 'checkbox'){
            return node;
        }
        if (node.setSelectionRange){
            node.setSelectionRange(range.start, range.end);
        } else if (node.createTextRange){
            node.createTextRange()
                .collapse(true)
                .moveEnd('character', range.start)
                .moveStart('character', range.end)
                .select();
        }
    }
});


odoo.define('sale_extensions.ListRenderer', function (require) {
    "use strict";

    var ListRenderer = require('web.ListRenderer');

    return ListRenderer.include({
        _onSortColumn: function (event) {
            var name = $(event.currentTarget).data('name');
            var models =  ["sale.order.line","account.invoice.line","purchase.order.line","stock.move"]
            if (models.includes(this.state.model) && name == 'position_number') {
                name = this.state.fields['number_int'] !== undefined ? "number_int" : "sequence_number";
                this.trigger_up('toggle_column_order', {
                    id: this.state.id,
                    name:  this.state.model == 'account.invoice.line' ? 'sequence_number' : name
                });
            }
            else {
                this._super.apply(this, arguments);
            }
        },
    });

});

odoo.define('sale_extensions.update_kanban', function (require) {
'use strict';

var core = require('web.core');
var KanbanRecord = require('web.KanbanRecord');

KanbanRecord.include({
    _openRecord: function () {
        if (this.modelName === 'sale.order' && this.$(".o_vs_sale_kanban_boxes a").length) {
            this.$('.o_vs_sale_kanban_boxes a').first().click();
        } else {
            this._super.apply(this, arguments);
        }
    },
});
});
