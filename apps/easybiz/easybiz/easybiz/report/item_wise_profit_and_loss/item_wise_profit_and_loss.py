import frappe
from frappe import _
from frappe.utils import flt, get_datetime

def execute(filters=None):
    filters = frappe._dict(filters or {})
    from_date = filters.get("from_date")
    to_date   = filters.get("to_date")
    
    if not from_date or not to_date:
        # Default to current month if dates not provided
        today = frappe.utils.today()
        from_date = from_date or frappe.utils.get_first_day(today)
        to_date = to_date or frappe.utils.get_last_day(today)

    # Define report columns (if not defined in JSON)
    columns = [
        {"fieldname": "date",        "label": _("Date"),        "fieldtype": "Datetime", "width": 150},
        {"fieldname": "item_code",   "label": _("Item Code"),   "fieldtype": "Link",     "options": "Item",     "width": 120},
        {"fieldname": "item_name",   "label": _("Item Name"),   "fieldtype": "Data",     "width": 150},
        {"fieldname": "month",       "label": _("Month"),       "fieldtype": "Data",     "width": 100},
        {"fieldname": "in_qty",      "label": _("In Qty"),      "fieldtype": "Float",    "width": 80,  "convertible": "qty"},
        {"fieldname": "out_qty",     "label": _("Out Qty"),     "fieldtype": "Float",    "width": 80,  "convertible": "qty"},
        {"fieldname": "balance_qty", "label": _("Balance Qty"), "fieldtype": "Float",    "width": 100, "convertible": "qty"},
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

    # Query cost (stock value difference) and stock movement by item and month
    stock_data = frappe.db.sql("""
        SELECT 
            sle.item_code,
            YEAR(sle.posting_date) AS year, 
            MONTH(sle.posting_date) AS month,
            SUM(CASE WHEN sle.actual_qty > 0 THEN sle.actual_qty ELSE 0 END) AS in_qty,
            SUM(CASE WHEN sle.actual_qty < 0 THEN ABS(sle.actual_qty) ELSE 0 END) AS out_qty,
            SUM(-CASE WHEN sle.actual_qty < 0 AND sle.voucher_type IN ('Delivery Note', 'Sales Invoice') 
                THEN sle.stock_value_difference ELSE 0 END) AS total_cost,
            MAX(sle.posting_datetime) AS last_transaction_date
        FROM `tabStock Ledger Entry` sle
        WHERE sle.docstatus < 2
          AND sle.is_cancelled = 0
          AND sle.posting_date >= %(from_date)s
          AND sle.posting_date <= %(to_date)s
        GROUP BY sle.item_code, year, month
    """, {"from_date": from_date, "to_date": to_date}, as_dict=True)

    # Get closing balance (qty_after_transaction) for each item/month combination
    balance_data = frappe.db.sql("""
        SELECT 
            sle.item_code,
            YEAR(sle.posting_date) AS year,
            MONTH(sle.posting_date) AS month,
            sle.qty_after_transaction,
            sle.posting_datetime,
            ROW_NUMBER() OVER (PARTITION BY sle.item_code, YEAR(sle.posting_date), MONTH(sle.posting_date) 
                ORDER BY sle.posting_datetime DESC, sle.creation DESC) AS rn
        FROM `tabStock Ledger Entry` sle
        WHERE sle.docstatus < 2
          AND sle.is_cancelled = 0
          AND sle.posting_date >= %(from_date)s
          AND sle.posting_date <= %(to_date)s
    """, {"from_date": from_date, "to_date": to_date}, as_dict=True)

    # Map (item, year, month) to stock data
    stock_map = {}
    for row in stock_data:
        key = (row.item_code, row.year, row.month)
        stock_map[key] = {
            "in_qty": flt(row.in_qty or 0),
            "out_qty": flt(row.out_qty or 0),
            "total_cost": flt(row.total_cost or 0),
            "last_transaction_date": row.last_transaction_date
        }

    # Map (item, year, month) to closing balance
    balance_map = {}
    for row in balance_data:
        if row.rn == 1:  # Only take the last transaction of each item/month
            key = (row.item_code, row.year, row.month)
            balance_map[key] = flt(row.qty_after_transaction or 0)

    # Create a map of item names for lookup
    item_names_map = {}
    for row in sales_data:
        item_names_map[row.item_code] = row.item_name
    
    # Get item names for items in stock_data that might not be in sales_data
    all_item_codes = set()
    for row in sales_data:
        all_item_codes.add(row.item_code)
    for row in stock_data:
        all_item_codes.add(row.item_code)
        if row.item_code not in item_names_map:
            item_doc = frappe.db.get_value("Item", row.item_code, ["item_name"], as_dict=True)
            if item_doc:
                item_names_map[row.item_code] = item_doc.item_name or row.item_code
    
    # Create a combined set of keys from both sales and stock data
    all_keys = set()
    sales_map = {}
    for row in sales_data:
        key = (row.item_code, row.year, row.month)
        all_keys.add(key)
        sales_map[key] = row
    
    for row in stock_data:
        key = (row.item_code, row.year, row.month)
        all_keys.add(key)
    
    # Combine sales, cost, and stock movement data
    data = []
    for key in all_keys:
        item_code, year, month = key
        sales_info = sales_map.get(key, {})
        stock_info = stock_map.get(key, {})
        
        total_qty = flt(sales_info.get("total_qty") or 0)
        total_sales = flt(sales_info.get("total_sales") or 0)
        total_cost = stock_info.get("total_cost", 0)
        in_qty = stock_info.get("in_qty", 0)
        out_qty = stock_info.get("out_qty", 0)
        balance_qty = balance_map.get(key, 0)
        date = stock_info.get("last_transaction_date") or frappe.utils.get_datetime(f"{year}-{month}-01 00:00:00")
        profit = total_sales - total_cost
        
        # Format month as "Month YYYY"
        try:
            month_label = "{:%B %Y}".format(frappe.utils.parse_date(f"{year}-{month}-01"))
        except:
            month_label = f"{month}/{year}"
        
        data.append({
            "date":        date,
            "item_code":   item_code,
            "item_name":   item_names_map.get(item_code, item_code),
            "month":       month_label,
            "in_qty":      in_qty,
            "out_qty":     out_qty,
            "balance_qty": balance_qty,
            "total_qty":   total_qty,
            "total_sales": total_sales,
            "total_cost":  total_cost,
            "profit":      profit
        })

    # Sort data by item and month
    data.sort(key=lambda r: (r["item_code"], r["month"]))
    return columns, data
