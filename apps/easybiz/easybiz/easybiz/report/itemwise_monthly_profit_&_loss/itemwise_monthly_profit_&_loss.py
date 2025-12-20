import frappe
from frappe.utils import nowdate

def execute(filters=None):
    if not filters:
        filters = {}

    from_date = filters.get("from_date") or frappe.utils.add_days(nowdate(), -30)
    to_date = filters.get("to_date") or nowdate()

    # ----------------------------------------
    # 1) SALES DATA (Correct & working)
    # ----------------------------------------
    sales = frappe.db.sql("""
        SELECT
            sii.item_code,
            sii.item_name,
            sii.stock_uom,
            SUM(sii.qty) AS sold_qty,
            SUM(sii.net_amount) AS total_sales
        FROM
            `tabSales Invoice` si
        JOIN
            `tabSales Invoice Item` sii ON si.name = sii.parent
        WHERE
            si.docstatus = 1
            AND si.posting_date BETWEEN %s AND %s
        GROUP BY sii.item_code
    """, (from_date, to_date), as_dict=1)

    result = []

    for s in sales:
        item = s.item_code

        # ----------------------------------------
        # 2) PURCHASE DATA (EXACT SAME LOGIC AS SALES)
        # ----------------------------------------
        purchase = frappe.db.sql("""
            SELECT
                SUM(pii.qty) AS purchased_qty,
                SUM(pii.base_net_amount) AS purchase_amount
            FROM
                `tabPurchase Invoice` pi
            JOIN
                `tabPurchase Invoice Item` pii ON pi.name = pii.parent
            WHERE
                pi.docstatus = 1
                AND pii.item_code = %s
                AND pi.posting_date BETWEEN %s AND %s
        """, (item, from_date, to_date), as_dict=1)[0]

        total_purchase_cost = purchase.purchase_amount or 0

        # ----------------------------------------
        # 3) PROFIT CALCULATION
        # ----------------------------------------
        profit = s.total_sales - total_purchase_cost
        profit_percent = (profit / s.total_sales * 100) if s.total_sales else 0

        # ----------------------------------------
        # 4) FINAL ROW
        # ----------------------------------------
        result.append({
            "item_code": s.item_code,
            "item_name": s.item_name,
            "stock_uom": s.stock_uom,
            "sold_qty": s.sold_qty,
            "total_sales": s.total_sales,
            "purchase_cost": total_purchase_cost,
            "profit": profit,
            "profit_percent": profit_percent
        })

    # ----------------------------------------
    # 5) COLUMNS
    # ----------------------------------------
    columns = [
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": "UOM", "fieldname": "stock_uom", "fieldtype": "Data", "width": 80},
        {"label": "Sold Qty", "fieldname": "sold_qty", "fieldtype": "Float", "width": 100},
        {"label": "Total Sales", "fieldname": "total_sales", "fieldtype": "Currency", "width": 130},
        {"label": "Purchase Cost", "fieldname": "purchase_cost", "fieldtype": "Currency", "width": 130},
        {"label": "Profit", "fieldname": "profit", "fieldtype": "Currency", "width": 130},
        {"label": "Profit %", "fieldname": "profit_percent", "fieldtype": "Percent", "width": 120},
    ]

    return columns, result
