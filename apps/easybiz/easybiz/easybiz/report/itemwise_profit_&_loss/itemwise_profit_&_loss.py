import frappe
from datetime import datetime, timedelta
from frappe.utils import flt

# Global memory for rolling purchase rates
last_purchase_rate = {}

def get_columns():
    return [
        {"label": "Date", "fieldname": "date", "fieldtype": "Datetime", "width": 150},
        {"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},

        {"label": "Opening Stock", "fieldname": "opening_qty", "fieldtype": "Float", "width": 110, "convertible": "qty"},
        {"label": "In Qty", "fieldname": "in_qty", "fieldtype": "Float", "width": 110, "convertible": "qty"},
        {"label": "Out Qty", "fieldname": "out_qty", "fieldtype": "Float", "width": 110, "convertible": "qty"},
        {"label": "Balance Qty", "fieldname": "balance_qty", "fieldtype": "Float", "width": 110, "convertible": "qty"},

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
    Uses same filters as Stock Ledger Report: docstatus < 2 and is_cancelled = 0
    """
    result = frappe.db.sql("""
        SELECT qty_after_transaction
        FROM `tabStock Ledger Entry`
        WHERE docstatus < 2
          AND is_cancelled = 0
          AND item_code = %s
          AND posting_date <= %s
        ORDER BY posting_date DESC, posting_time DESC, creation DESC
        LIMIT 1
    """, (item_code, date_str))
    return flt(result[0][0]) if result and result[0][0] is not None else 0

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
    Uses same calculation: in_qty = max(actual_qty, 0), out_qty = min(actual_qty, 0) shown as positive
    Uses same filters: docstatus < 2 and is_cancelled = 0
    Also gets weighted average incoming_rate for IN transactions (purchases)
    """
    result = frappe.db.sql("""
        SELECT 
            SUM(CASE WHEN actual_qty > 0 THEN actual_qty ELSE 0 END) as in_qty,
            SUM(CASE WHEN actual_qty < 0 THEN ABS(actual_qty) ELSE 0 END) as out_qty,
            MAX(posting_datetime) as last_posting_datetime,
            SUM(CASE WHEN actual_qty > 0 AND incoming_rate > 0 THEN actual_qty * incoming_rate ELSE 0 END) / 
            NULLIF(SUM(CASE WHEN actual_qty > 0 AND incoming_rate > 0 THEN actual_qty ELSE 0 END), 0) as avg_incoming_rate
        FROM `tabStock Ledger Entry`
        WHERE docstatus < 2
          AND is_cancelled = 0
          AND item_code = %s
          AND posting_date = %s
    """, (item_code, date_str), as_dict=True)
    
    if result and result[0]:
        return {
            'in_qty': flt(result[0].get('in_qty') or 0),
            'out_qty': flt(result[0].get('out_qty') or 0),
            'last_posting_datetime': result[0].get('last_posting_datetime'),
            'avg_incoming_rate': flt(result[0].get('avg_incoming_rate')) if result[0].get('avg_incoming_rate') else None
        }
    return {'in_qty': 0, 'out_qty': 0, 'last_posting_datetime': None, 'avg_incoming_rate': None}

def get_purchase_rate_for_date(item_code, date_str):
    """
    Get weighted average incoming_rate (purchase rate) from Stock Ledger Entry for IN transactions on this date.
    Uses incoming_rate from Stock Ledger Entry, same as Stock Ledger Report.
    """
    result = frappe.db.sql("""
        SELECT SUM(CASE WHEN actual_qty > 0 AND incoming_rate > 0 THEN actual_qty * incoming_rate ELSE 0 END) / 
               NULLIF(SUM(CASE WHEN actual_qty > 0 AND incoming_rate > 0 THEN actual_qty ELSE 0 END), 0) as avg_rate
        FROM `tabStock Ledger Entry`
        WHERE docstatus < 2
          AND is_cancelled = 0
          AND item_code = %s
          AND posting_date = %s
          AND actual_qty > 0
          AND incoming_rate > 0
    """, (item_code, date_str), as_dict=False)
    if result and result[0] and result[0][0] is not None:
        return round(flt(result[0][0]), 4)
    return None

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
    Uses same calculation approach as Stock Ledger Report.
    """
    global last_purchase_rate

    # Get stock movements from Stock Ledger (like Stock Ledger Report)
    stock_data = get_stock_movements_from_ledger(item_code, date_str)
    in_qty = stock_data['in_qty']
    out_qty = stock_data['out_qty']
    last_posting_datetime = stock_data.get('last_posting_datetime')
    avg_incoming_rate = stock_data.get('avg_incoming_rate')
    
    # IMPORTANT: Get the actual closing balance from Stock Ledger Entry
    # to ensure it matches ERPNext's Stock Ledger Report
    actual_closing = get_closing_balance_from_ledger(item_code, date_str)
    
    # Use actual closing balance from ledger (this is the source of truth)
    balance_qty = actual_closing

    # Skip if no activity at all (no opening, no movements, no balance)
    if opening == 0 and in_qty == 0 and out_qty == 0 and balance_qty == 0:
        return None, balance_qty

    # Use posting_datetime for date (like Stock Ledger Report)
    # If no transactions on this date, use date_str at start of day as datetime
    if last_posting_datetime:
        date_value = last_posting_datetime
    else:
        # No transactions, use start of day as datetime
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        date_value = datetime.combine(date_obj.date(), datetime.min.time())

    # Get purchase rate from incoming_rate in Stock Ledger Entry (like Stock Ledger Report)
    # First check if we have incoming_rate from today's IN transactions
    if avg_incoming_rate:
        last_purchase_rate[item_code] = round(flt(avg_incoming_rate), 4)
        purchase_rate = last_purchase_rate[item_code]
    else:
        # No incoming_rate today, try to get from get_purchase_rate_for_date (for consistency)
        purchase_rate_today = get_purchase_rate_for_date(item_code, date_str)
        if purchase_rate_today:
            last_purchase_rate[item_code] = purchase_rate_today
            purchase_rate = purchase_rate_today
        else:
            # Use cached rate from previous days
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

    row = {
        "date": date_value,
        "item_code": item_code,
        "opening_qty": flt(opening),
        "in_qty": flt(in_qty),
        "out_qty": flt(out_qty),
        "balance_qty": flt(balance_qty),
        "purchase_rate": purchase_rate,
        "sales_rate": sales_rate,
        "purchase_amount": purchase_amount,
        "sales_amount": sales_amount,
        "profit": profit,
        "profit_percent": profit_percent
    }
    
    return row, balance_qty


def execute(filters=None):
    global last_purchase_rate
    
    if not filters:
        filters = frappe._dict({})
    else:
        filters = frappe._dict(filters)

    columns = get_columns()
    data = []
    
    if not filters.get("from_date") or not filters.get("to_date"):
        return columns, data

    start = datetime.strptime(filters.from_date, "%Y-%m-%d")
    end = datetime.strptime(filters.to_date, "%Y-%m-%d")

    # Get items - if item filter specified, use it; otherwise get items with activity in date range
    if filters.get("item"):
        items = [filters.item]
    else:
        # Get items that have stock movements or sales in the date range
        items_with_movements = frappe.db.sql("""
            SELECT DISTINCT item_code
            FROM `tabStock Ledger Entry`
            WHERE docstatus < 2
              AND is_cancelled = 0
              AND posting_date BETWEEN %s AND %s
        """, (filters.from_date, filters.to_date), as_dict=False)
        
        items_with_sales = frappe.db.sql("""
            SELECT DISTINCT sii.item_code
            FROM `tabSales Invoice Item` sii
            JOIN `tabSales Invoice` si ON si.name = sii.parent
            WHERE si.docstatus = 1
              AND si.posting_date BETWEEN %s AND %s
        """, (filters.from_date, filters.to_date), as_dict=False)
        
        # Combine and deduplicate
        all_items = set()
        for row in items_with_movements:
            if row[0]:
                all_items.add(row[0])
        for row in items_with_sales:
            if row[0]:
                all_items.add(row[0])
        
        items = list(all_items)
    
    if not items:
        return columns, data

    # Preload last purchase rates before the date range
    # Get incoming_rate from Stock Ledger Entry (same as Stock Ledger Report)
    last_purchase_rate = {}
    for item in items:
        # Get the last incoming_rate from Stock Ledger Entry before the start date
        # This is the purchase rate from the most recent IN transaction
        rate = frappe.db.sql("""
            SELECT incoming_rate
            FROM `tabStock Ledger Entry`
            WHERE docstatus < 2
              AND is_cancelled = 0
              AND item_code = %s
              AND posting_date < %s
              AND actual_qty > 0
              AND incoming_rate > 0
            ORDER BY posting_date DESC, posting_time DESC, creation DESC
            LIMIT 1
        """, (item, filters.from_date), as_dict=False)
        last_purchase_rate[item] = round(flt(rate[0][0]), 4) if rate and rate[0] and rate[0][0] is not None else 0

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
