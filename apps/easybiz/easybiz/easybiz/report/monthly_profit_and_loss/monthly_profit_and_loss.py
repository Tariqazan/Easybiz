import frappe
from calendar import monthrange

def execute(filters=None):
    if not filters:
        filters = {}

    # Handle filters
    month_name_to_number = {
        "January": 1, "February": 2, "March": 3, "April": 4,
        "May": 5, "June": 6, "July": 7, "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12
    }

    year = int(filters.get("year", frappe.utils.now_datetime().year))
    month_name = filters.get("month")
    item_filter = filters.get("item")

    month = month_name_to_number.get(month_name.title() if month_name else "April")
    if not month:
        frappe.throw("Invalid month selected.")

    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{monthrange(year, month)[1]}"

    conditions = f"""
        sii.docstatus = 1 AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
    """
    params = {"from_date": start_date, "to_date": end_date}

    if item_filter:
        conditions += " AND sii.item_code = %(item_code)s"
        params["item_code"] = item_filter

    data = frappe.db.sql(f"""
        SELECT
            sii.item_code,
            sii.item_name,
            SUM(sii.qty) AS total_qty,
            SUM(sii.base_net_amount) AS total_sales
        FROM `tabSales Invoice Item` sii
        JOIN `tabSales Invoice` si ON sii.parent = si.name
        WHERE {conditions}
        GROUP BY sii.item_code, sii.item_name
        ORDER BY total_sales DESC
    """, params, as_dict=True)

    columns = [
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 180},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 240},
        {"label": "Total Qty", "fieldname": "total_qty", "fieldtype": "Float", "width": 120},
        {"label": "Total Sales (Base)", "fieldname": "total_sales", "fieldtype": "Currency", "width": 160},
    ]

    return columns, data
