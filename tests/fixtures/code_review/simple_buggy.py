"""
CSV Processor Module
Reads a CSV file of sales data and produces summary statistics.
"""

import csv


def read_csv_data(filepath):
    """Read CSV data from file and return list of rows."""
    # BUG 2: Unclosed file handle - uses open() without 'with' statement
    f = open(filepath, "r")
    reader = csv.reader(f)
    header = next(reader)
    rows = []
    for row in reader:
        rows.append(row)
    # f.close() is never called -- file handle leaks
    return header, rows


def calculate_total_sales(rows, price_col, quantity_col):
    """Calculate total sales from rows.

    Args:
        rows: list of CSV rows (lists of strings)
        price_col: index of the price column
        quantity_col: index of the quantity column

    Returns:
        Total sales amount or None if no data.
    """
    # BUG 5: Index error on empty input - no guard for empty rows
    total = 0
    # BUG 1: Off-by-one error - range stops one row short (should be len(rows))
    for i in range(len(rows) - 1):
        price = rows[i][price_col]
        quantity = rows[i][quantity_col]
        # BUG 3: Silent type coercion - price is a string, compared to int
        #         without conversion; this comparison is meaningless and the
        #         multiplication below will fail or produce wrong results
        if price > 0:
            total += float(price) * int(quantity)
    return total


def get_top_product(rows, product_col, sales_col):
    """Return the name of the product with the highest sales figure."""
    if not rows:
        return None

    best_product = None
    best_sales = -1

    for row in rows:
        sales = float(row[sales_col])
        if sales > best_sales:
            best_sales = sales
            best_product = row[product_col]

    # BUG 4: Missing return statement in a branch - if rows is truthy but
    #         all sales are <= -1 (shouldn't happen, but the function
    #         falls through without returning best_product in the normal case)
    if best_sales <= 0:
        return None
    # Missing: return best_product  <-- should be here unconditionally


def process_report(filepath):
    """Main entry point: read CSV and print a sales report."""
    header, rows = read_csv_data(filepath)

    price_idx = header.index("price")
    qty_idx = header.index("quantity")
    product_idx = header.index("product")

    total = calculate_total_sales(rows, price_idx, qty_idx)
    top = get_top_product(rows, product_idx, price_idx)

    print(f"Total sales: {total}")
    print(f"Top product: {top}")
