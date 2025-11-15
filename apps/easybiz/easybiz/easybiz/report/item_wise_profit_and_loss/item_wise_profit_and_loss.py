import frappe
from frappe import _

def execute(filters=None):
    filters = frappe._dict(filters or {})
    from_date = filters.get("from_date")
    to_date   = filters.get("to_date")

    # Define report columns (if not defined in JSON)
    columns = [
        {"fieldname": "item_code",   "label": _("Item Code"),   "fieldtype": "Link",     "options": "Item",     "width": 120},
        {"fieldname": "item_name",   "label": _("Item Name"),   "fieldtype": "Data",     "width": 150},
        {"fieldname": "month",       "label": _("Month"),       "fieldtype": "Data",     "width": 100},
        {"fieldname": "total_qty",   "label": _("Total Qty Sold"),      "fieldtype": "Float",    "width": 100},
        {"fieldname": "total_sales", "label": _("Total Sales Amt"),     "fieldtype": "Currency", "width": 120},
        {"fieldname": "total_cost",  "label": _("Total Buying Cost"),   "fieldtype": "Currency", "width": 120},
        {"fieldname": "profit",      "label": _("Total Profit/Loss"),   "fieldtype": "Currency", "width": 120},
    ]

    # Query sales by item and month
    sales_data = frappe.db.sql("""
        SELECT 
            sii.item_code, 
            sii.item_name,
            YEAR(si.posting_date) AS year, 
            MONTH(si.posting_date) AS month,
            SUM(sii.qty)    AS total_qty,
            SUM(sii.amount) AS total_sales
        FROM `tabSales Invoice` si
        JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND si.posting_date >= %(from_date)s
          AND si.posting_date <= %(to_date)s
        GROUP BY sii.item_code, year, month
    """, {"from_date": from_date, "to_date": to_date}, as_dict=True)

    # Query cost (stock value difference) by item and month
    cost_data = frappe.db.sql("""
        SELECT 
            sle.item_code,
            YEAR(sle.posting_date) AS year, 
            MONTH(sle.posting_date) AS month,
            SUM(-sle.stock_value_difference) AS total_cost
        FROM `tabStock Ledger Entry` sle
        WHERE sle.docstatus = 1
          AND sle.actual_qty < 0
          AND sle.voucher_type IN ('Delivery Note', 'Sales Invoice')
          AND sle.posting_date >= %(from_date)s
          AND sle.posting_date <= %(to_date)s
        GROUP BY sle.item_code, year, month
    """, {"from_date": from_date, "to_date": to_date}, as_dict=True)

    # Map (item, year, month) to cost
    cost_map = {}
    for row in cost_data:
        cost_map[(row.item_code, row.year, row.month)] = row.total_cost or 0

    # Combine sales and cost
    data = []
    for row in sales_data:
        if not row.total_qty:
            # Skip if no quantity sold (edge case)
            continue
        key = (row.item_code, row.year, row.month)
        total_cost = cost_map.get(key, 0)
        profit = row.total_sales - total_cost
        # Format month as "Month YYYY"
        month_label = "{:%B %Y}".format(frappe.utils.parse_date(f"{row.year}-{row.month}-01"))
        data.append({
            "item_code":   row.item_code,
            "item_name":   row.item_name,
            "month":       month_label,
            "total_qty":   row.total_qty,
            "total_sales": row.total_sales,
            "total_cost":  total_cost,
            "profit":      profit
        })

    # Optionally sort data by item and month
    data.sort(key=lambda r: (r["item_code"], r["month"]))
    return columns, data
