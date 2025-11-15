frappe.query_reports["Monthly Itemwise Profit Report"] = {
    filters: [
        {
            fieldname: "month",
            label: "Month",
            fieldtype: "Select",
            options: [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ],
            default: (function () {
                const today = new Date();
                return today.toLocaleString("default", { month: "long" });
            })()
        },
        {
            fieldname: "year",
            label: "Year",
            fieldtype: "Int",
            default: new Date().getFullYear()
        },
        {
            fieldname: "item",
            label: "Item",
            fieldtype: "Link",
            options: "Item",
            reqd: 0
        }
    ]
};
