import frappe
from datetime import datetime, timedelta

# Global memory for rolling purchase rates
last_purchase_rate = {}

def get_columns():
    return [
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 95},
        {"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},

        {"label": "Opening Stock", "fieldname": "opening_qty", "fieldtype": "Float", "width": 110},
        {"label": "In Qty", "fieldname": "in_qty", "fieldtype": "Float", "width": 110},
        {"label": "Out Qty", "fieldname": "out_qty", "fieldtype": "Float", "width": 110},
        {"label": "Balance Qty", "fieldname": "balance_qty", "fieldtype": "Float", "width": 110},

        {"label": "Purchase Rate", "fieldname": "purchase_rate", "fieldtype": "Currency", "width": 110},
        {"label": "Sales Rate", "fieldname": "sales_rate", "fieldtype": "Currency", "width": 110},

        {"label": "Purchase Amount", "fieldname": "purchase_amount", "fieldtype": "Currency", "width": 130},
        {"label": "Sales Amount", "fieldname": "sales_amount", "fieldtype": "Currency", "width": 130},

        {"label": "Daily Profit/Loss", "fieldname": "profit", "fieldtype": "Currency", "width": 130},
        {"label": "Profit %", "fieldname": "profit_percent", "fieldtype": "Float", "width": 90},
    ]

# -----------------------------------------------------------------
# STOCK CALCULATIONS - Exactly matching Stock Ledger Report
# -----------------------------------------------------------------
def get_closing_balance_from_ledger(item_code, date_str):
    """
    Get the CLOSING balance (qty_after_transaction) of the LAST transaction 
    on or before this date. This is ERPNext's standard approach.
    The closing balance of previous day = opening balance of current day.
    """
    result = frappe.db.sql("""
        SELECT qty_after_transaction
        FROM `tabStock Ledger Entry`
        WHERE docstatus = 1
          AND item_code = %s
          AND posting_date <= %s
        ORDER BY posting_date DESC, posting_time DESC, creation DESC
        LIMIT 1
    """, (item_code, date_str))
    return result[0][0] if result else 0

def get_opening_stock_from_ledger(item_code, from_date):
    """
    Get opening stock BEFORE the from_date using Stock Ledger Entry.
    This is the closing balance of the day BEFORE from_date.
    """
    # Get the day before from_date
    from_date_obj = datetime.strptime(from_date, "%Y-%m-%d")
    previous_day = from_date_obj - timedelta(days=1)
    previous_day_str = previous_day.strftime("%Y-%m-%d")
    
    # Get closing balance of previous day
    return get_closing_balance_from_ledger(item_code, previous_day_str)

def get_stock_movements_from_ledger(item_code, date_str):
    """
    Get stock IN/OUT for the day from Stock Ledger Entry.
    This exactly matches how ERPNext's Stock Ledger Report calculates movements.
    """
    result = frappe.db.sql("""
        SELECT 
            SUM(CASE WHEN actual_qty > 0 THEN actual_qty ELSE 0 END) as in_qty,
            SUM(CASE WHEN actual_qty < 0 THEN ABS(actual_qty) ELSE 0 END) as out_qty
        FROM `tabStock Ledger Entry`
        WHERE docstatus = 1
          AND item_code = %s
          AND posting_date = %s
    """, (item_code, date_str), as_dict=True)
    
    if result and result[0]:
        return {
            'in_qty': result[0].get('in_qty') or 0,
            'out_qty': result[0].get('out_qty') or 0
        }
    return {'in_qty': 0, 'out_qty': 0}

def get_purchase_rate_for_date(item_code, date_str):
    """
    Get weighted average purchase rate for purchases on this date.
    """
    result = frappe.db.sql("""
        SELECT SUM(pii.qty * pii.rate) / NULLIF(SUM(pii.qty), 0)
        FROM `tabPurchase Invoice Item` pii
        JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE pii.item_code = %s
          AND pi.posting_date = %s
          AND pi.docstatus = 1
    """, (item_code, date_str))
    return round(result[0][0], 4) if result and result[0][0] else None

def get_sales_details_for_date(item_code, date_str):
    """
    Get sales quantity and amount for the date.
    """
    result = frappe.db.sql("""
        SELECT 
            IFNULL(SUM(sii.qty), 0) as qty,
            IFNULL(SUM(sii.amount), 0) as amount
        FROM `tabSales Invoice Item` sii
        JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE sii.item_code = %s
          AND si.posting_date = %s
          AND si.docstatus = 1
    """, (item_code, date_str), as_dict=True)
    
    return result[0] if result else {'qty': 0, 'amount': 0}

def build_row(item_code, date_str, opening):
    """
    Build a single row for the report.
    Returns: (row_data, closing_balance)
    """
    global last_purchase_rate

    # Get stock movements from Stock Ledger (like Stock Ledger Report)
    stock_data = get_stock_movements_from_ledger(item_code, date_str)
    in_qty = stock_data['in_qty']
    out_qty = stock_data['out_qty']
    
    # Calculate balance exactly like ERPNext: Opening + In - Out
    balance_qty = opening + in_qty - out_qty
    
    # IMPORTANT: Get the actual closing balance from Stock Ledger Entry
    # to ensure it matches ERPNext's Stock Ledger Report
    actual_closing = get_closing_balance_from_ledger(item_code, date_str)
    
    # Use actual closing balance from ledger (this is the source of truth)
    balance_qty = actual_closing

    # Skip if no activity
    if opening == 0 and in_qty == 0 and out_qty == 0:
        return None, balance_qty

    # Get purchase rate
    purchase_rate_today = get_purchase_rate_for_date(item_code, date_str)
    if purchase_rate_today:
        last_purchase_rate[item_code] = purchase_rate_today
        purchase_rate = purchase_rate_today
    else:
        purchase_rate = last_purchase_rate.get(item_code, 0)

    # Get sales details
    sales_data = get_sales_details_for_date(item_code, date_str)
    sales_qty = sales_data['qty']
    sales_amount = sales_data['amount']
    sales_rate = round(sales_amount / sales_qty, 4) if sales_qty > 0 else 0

    # Calculate profit/loss based on OUT quantity (actual sales/consumption)
    purchase_amount = round(out_qty * purchase_rate, 2)
    profit = round(sales_amount - purchase_amount, 2)
    profit_percent = round((profit / purchase_amount * 100), 2) if purchase_amount else 0

    row = [
        date_str,
        item_code,
        opening,
        in_qty,
        out_qty,
        balance_qty,
        purchase_rate,
        sales_rate,
        purchase_amount,
        sales_amount,
        profit,
        profit_percent
    ]
    
    return row, balance_qty


def execute(filters=None):
    global last_purchase_rate

    columns = get_columns()
    data = []

    start = datetime.strptime(filters.from_date, "%Y-%m-%d")
    end = datetime.strptime(filters.to_date, "%Y-%m-%d")

    items = [filters.item] if filters.get("item") else frappe.get_all("Item", pluck="name")

    # Preload last purchase rates before the date range
    last_purchase_rate = {}
    for item in items:
        rate = frappe.db.sql("""
            SELECT pii.rate
            FROM `tabPurchase Invoice Item` pii
            JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
            WHERE pii.item_code = %s
              AND pi.docstatus = 1
              AND pi.posting_date < %s
            ORDER BY pi.posting_date DESC, pi.name DESC
            LIMIT 1
        """, (item, filters.from_date))
        last_purchase_rate[item] = round(rate[0][0], 4) if rate else 0

    # Get opening stock from Stock Ledger Entry (closing balance of previous day)
    opening_stocks = {}
    first_date = start.strftime("%Y-%m-%d")
    for item in items:
        opening_stocks[item] = get_opening_stock_from_ledger(item, first_date)

    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        for item in items:
            row, closing_balance = build_row(item, date_str, opening_stocks[item])
            if row:
                data.append(row)
            
            # CRITICAL: Next day's opening = Today's closing balance
            # This is exactly how ERPNext Stock Ledger works
            opening_stocks[item] = closing_balance
            
        current += timedelta(days=1)

    return columns, data
