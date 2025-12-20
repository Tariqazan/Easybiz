frappe.query_reports["Itemwise Profit & Loss"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "item",
            "label": __("Item"),
            "fieldtype": "Link",
            "options": "Item",
            "reqd": 0
        }
    ],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        // Highlight negative profit in red
        if (column.fieldname === "profit" && data && data.profit < 0) {
            value = `<span style="color:red;">${value}</span>`;
        }

        // Highlight negative profit percentage in red
        if (column.fieldname === "profit_percent" && data && data.profit_percent < 0) {
            value = `<span style="color:red;">${value}%</span>`;
        }

        return value;
    }
};
