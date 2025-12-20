// Copyright (c) 2025
// For license information, please see license.txt

frappe.query_reports["Itemwise Monthly Profit & Loss"] = {
    filters: [
        {
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -30)
        },
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        }
    ],
    onload(report) {
        report.page.add_inner_button("Last 30 Days", () => {
            report.set_filter_value("from_date",
                frappe.datetime.add_days(frappe.datetime.get_today(), -30)
            );
            report.set_filter_value("to_date", frappe.datetime.get_today());
        });
    }
};
