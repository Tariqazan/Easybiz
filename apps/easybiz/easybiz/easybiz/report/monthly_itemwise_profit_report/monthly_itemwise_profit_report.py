import frappe
from frappe.utils import get_last_day

def execute(filters=None):
    if not filters:
        filters = {}

    # Month name to number map
    month_name_to_number = {
        "January": 1, "February": 2, "March": 3, "April": 4,
        "May": 5, "June": 6, "July": 7, "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12
    }

    # Get year and month from filters
    year = int(filters.get("year"))
    month = month_name_to_number.get(filters.get("month"), 1)
    item_filter = filters.get("item_code")

    # Calculate date range
    from_date = f"{year}-{month:02d}-01"
    to_date = get_last_day(from_date)

    # Prepare sales query conditions
    conditions = "si.docstatus = 1 AND si.posting_date BETWEEN %s AND %s"
    params = [from_date, to_date]

    if item_filter:
        conditions += " AND sii.item_code = %s"
        params.append(item_filter)

    # 1. Get sold items and sales amount
    sold_items = frappe.db.sql(f"""
        SELECT
            sii.item_code,
            sii.item_name,
            SUM(sii.qty) AS sold_qty,
            SUM(sii.base_net_amount) AS sales_amount
        FROM `tabSales Invoice` si
        JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE {conditions}
        GROUP BY sii.item_code
    """, tuple(params), as_dict=1)

    data = []

    for item in sold_items:
        item_code = item.item_code
        sold_qty = item.sold_qty
        sales_amount = item.sales_amount

        # 2. Get average purchase rate (historical till end of month)
        purchase_info = frappe.db.sql("""
            SELECT
                SUM(pii.qty) AS total_purchase_qty,
                SUM(pii.base_net_amount) AS total_purchase_amount
            FROM `tabPurchase Invoice` pi
            JOIN `tabPurchase Invoice Item` pii ON pi.name = pii.parent
            WHERE
                pi.docstatus = 1
                AND pii.item_code = %s
                AND pi.posting_date <= %s
        """, (item_code, to_date), as_dict=1)[0]

        total_purchase_qty = purchase_info.total_purchase_qty or 0
        total_purchase_amount = purchase_info.total_purchase_amount or 0

        avg_purchase_rate = (
            total_purchase_amount / total_purchase_qty
            if total_purchase_qty else 0
        )

        purchase_cost = sold_qty * avg_purchase_rate
        profit = sales_amount - purchase_cost
        profit_percent = (profit / purchase_cost * 100) if purchase_cost else 0

        data.append({
            "item_code": item_code,
            "sold_qty": sold_qty,
            "sales_amount": sales_amount,
            "total_purchase": total_purchase_amount,
            "avg_rate": avg_purchase_rate,
            "cost_of_sold": purchase_cost,
            "profit": profit,
            "profit_percent": f"{profit_percent:.2f}%",
        })

    # Define clean, fixed-width columns (DataTable-compliant)
    columns = [
        {
            "label": "Item Code",
            "fieldname": "item_code",
            "fieldtype": "Data",
            "width": 160
        },
        {
            "label": "Qty Sold",
            "fieldname": "sold_qty",
            "fieldtype": "Float",
            "precision": 2,
            "width": 150
        },
        {
            "label": "Sales Amount",
            "fieldname": "sales_amount",
            "fieldtype": "Currency",
            "width": 200
        },
        {
            "label": "Total Purchase (All Time)",
            "fieldname": "total_purchase",
            "fieldtype": "Currency",
            "width": 200
        },
        {
            "label": "Avg Purchase Rate",
            "fieldname": "avg_rate",
            "fieldtype": "Currency",
            "width": 200
        },
        {
            "label": "Cost of Sold Qty",
            "fieldname": "cost_of_sold",
            "fieldtype": "Currency",
            "width": 200
        },
        {
            "label": "Profit",
            "fieldname": "profit",
            "fieldtype": "Currency",
            "width": 200
        },
        {
            "label": "Profit %",
            "fieldname": "profit_percent",
            "fieldtype": "Data",
            "width": 150
        }
    ]

    return columns, data
