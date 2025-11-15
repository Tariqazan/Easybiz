import frappe
from frappe.utils import now_datetime, get_last_day

def execute(filters=None):
    if not filters:
        filters = {}

    # Month/Year filters
    today = now_datetime()
    raw_month = filters.get("month")
    year = int(filters.get("year") or today.year)

    MONTH_NAME_TO_NUMBER = {
        "January": 1, "February": 2, "March": 3, "April": 4,
        "May": 5, "June": 6, "July": 7, "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12
    }
    month = MONTH_NAME_TO_NUMBER.get(raw_month, today.month)

    start_date = f"{year}-{month:02d}-01"
    end_date = get_last_day(start_date)

    # Step 1: Get sold items from sales invoice
    sales = frappe.db.sql("""
        SELECT
            sii.item_code,
            sii.item_name,
            sii.stock_uom,
            SUM(sii.qty) AS sold_qty,
            SUM(sii.amount) AS total_sales
        FROM
            `tabSales Invoice` si
        JOIN
            `tabSales Invoice Item` sii ON si.name = sii.parent
        WHERE
            si.docstatus = 1
            AND si.posting_date BETWEEN %s AND %s
        GROUP BY sii.item_code
    """, (start_date, end_date), as_dict=1)

    result = []

    for s in sales:
        sold_qty = s.sold_qty
        cost = 0

        # Step 2: Get purchase invoices in FIFO order
        purchases = frappe.db.sql("""
            SELECT
                pii.qty,
                pii.valuation_rate,
                pii.amount
            FROM
                `tabPurchase Invoice` pi
            JOIN
                `tabPurchase Invoice Item` pii ON pi.name = pii.parent
            WHERE
                pi.docstatus = 1
                AND pii.item_code = %s
                AND pi.posting_date <= %s
            ORDER BY
                pi.posting_date ASC, pi.name ASC
        """, (s.item_code, end_date), as_dict=1)

        remaining = sold_qty

        # Step 3: Apply FIFO costing
        for p in purchases:
            if remaining <= 0:
                break
            consume_qty = min(remaining, p.qty)
            cost += consume_qty * (p.valuation_rate or 0)
            remaining -= consume_qty

        profit = s.total_sales - cost

        result.append({
            "item_code": s.item_code,
            "item_name": s.item_name,
            "stock_uom": s.stock_uom,
            "sold_qty": sold_qty,
            "total_sales": s.total_sales,
            "estimated_cost": cost,
            "profit": profit
        })

    # Columns
    columns = [
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": "UOM", "fieldname": "stock_uom", "fieldtype": "Data", "width": 80},
        {"label": "Sold Qty", "fieldname": "sold_qty", "fieldtype": "Float", "width": 100},
        {"label": "Total Sales", "fieldname": "total_sales", "fieldtype": "Currency", "width": 130},
        {"label": "Estimated Cost", "fieldname": "estimated_cost", "fieldtype": "Currency", "width": 130},
        {"label": "Profit", "fieldname": "profit", "fieldtype": "Currency", "width": 130},
    ]

    return columns, result
