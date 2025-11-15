// Copyright (c) 2025, Tariqul Islam and contributors
// For license information, please see license.txt

frappe.query_reports["Itemwise Monthly Profit & Loss"] = {
    filters: [
        {
            fieldname: "month",
            label: "Month",
            fieldtype: "Select",
            options: [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ],
            default: frappe.datetime.str_to_obj(frappe.datetime.get_today()).toLocaleString('default', { month: 'long' })
        },
        {
            fieldname: "year",
            label: "Year",
            fieldtype: "Int",
            default: new Date().getFullYear()
        }
    ],
    onload: function(report) {
        // Map month name to number for server use
        report.page.add_inner_button("Refresh", () => {
            const filters = report.get_values();
            const monthNames = {
                "January": 1, "February": 2, "March": 3, "April": 4,
                "May": 5, "June": 6, "July": 7, "August": 8,
                "September": 9, "October": 10, "November": 11, "December": 12
            };

            filters.month = monthNames[filters.month];
            report.set_filter_value("month", filters.month);
        });
    }
};
