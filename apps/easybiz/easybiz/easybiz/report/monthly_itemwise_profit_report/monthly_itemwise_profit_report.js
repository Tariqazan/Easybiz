frappe.query_reports["Monthly Itemwise Profit Report"] = {
    filters: [
        {
            fieldname: "year",
            label: "Year",
            fieldtype: "Int",
            default: new Date().getFullYear(),
            reqd: 1
        },
        {
            fieldname: "month",
            label: "Month",
            fieldtype: "Select",
            options: [
                "January", "February", "March", "April",
                "May", "June", "July", "August",
                "September", "October", "November", "December"
            ],
            default: frappe.datetime.str_to_obj(frappe.datetime.get_today()).toLocaleString('default', { month: 'long' }),
            reqd: 1
        },
        {
            fieldname: "item_code",
            label: "Item",
            fieldtype: "Link",
            options: "Item"
        }
    ],



formatter: function(value, row, column, data, default_formatter) {
    value = default_formatter(value, row, column, data);

    if (column.fieldname === "profit") {
        const profit = parseFloat(data.profit || 0);
        if (profit > 0) {
            value = `<span style="color: green;">${value}</span>`;
        } else if (profit < 0) {
            value = `<span style="color: red;">${value}</span>`;
        }
    }

    return value;
}

};
