import frappe
from calendar import monthrange

def get_stock_on_date(item_code, warehouse, date):
    result = frappe.db.sql("""
        SELECT SUM(actual_qty)
        FROM `tabStock Ledger Entry`
        WHERE item_code = %s 
        AND warehouse = %s
        AND posting_date <= %s
    """, (item_code, warehouse, date))

    return result[0][0] or 0


def execute(filters=None):
    if not filters:
        filters = {}

    month_name_to_number = {
        "January": 1, "February": 2, "March": 3, "April": 4,
        "May": 5, "June": 6, "July": 7, "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12
    }

    year = int(filters.get("year", frappe.utils.now_datetime().year))
    month = month_name_to_number.get(filters.get("month"))
    warehouse = filters.get("warehouse")

    if not month:
        frappe.throw("Invalid month")

    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{monthrange(year, month)[1]}"

    item_filter = filters.get("item")

    conditions = """
        sii.docstatus = 1
        AND si.posting_date BETWEEN %(from)s AND %(to)s
    """

    params = {"from": start_date, "to": end_date}

    if item_filter:
        conditions += " AND sii.item_code = %(item)s"
        params["item"] = item_filter

    data = frappe.db.sql(f"""
        SELECT
            sii.item_code,
            sii.item_name,
            SUM(sii.qty) AS total_qty,
            SUM(sii.base_net_amount) AS total_sales
        FROM `tabSales Invoice Item` sii
        JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE {conditions}
        GROUP BY sii.item_code, sii.item_name
        ORDER BY total_sales DESC
    """, params, as_dict=True)

    # Add only opening stock (simple)
    for row in data:
        row["opening_stock"] = get_stock_on_date(
            row["item_code"], 
            warehouse,
            start_date
        )

    columns = [
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 220},
        {"label": "Opening Stock", "fieldname": "opening_stock", "fieldtype": "Float", "width": 130},
        {"label": "Sold Qty", "fieldname": "total_qty", "fieldtype": "Float", "width": 110},
        {"label": "Total Sales (Base)", "fieldname": "total_sales", "fieldtype": "Currency", "width": 140},
    ]

    return columns, data
