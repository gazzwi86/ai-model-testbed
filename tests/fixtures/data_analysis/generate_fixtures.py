#!/usr/bin/env python3
"""Generate test fixture data files for data analysis benchmarks.

Produces deterministic test data using seed 42. Run this script from its
own directory (or any directory -- it writes output next to itself).
"""

import csv
import json
import os
import random
import string
from pathlib import Path

SEED = 42
OUTPUT_DIR = Path(__file__).resolve().parent


def _rand_name(rng: random.Random) -> str:
    first_names = [
        "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace",
        "Hector", "Irene", "Jack", "Karen", "Leo", "Mona", "Nick",
        "Olivia", "Paul", "Quinn", "Rachel", "Sam", "Tina",
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
        "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez",
        "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore",
        "Jackson", "Martin",
    ]
    return f"{rng.choice(first_names)} {rng.choice(last_names)}"


# ── simple_data.json ────────────────────────────────────────────────

def generate_simple_data() -> None:
    rng = random.Random(SEED)
    departments = ["Engineering", "Sales", "Marketing", "HR", "Finance"]
    records = []
    for i in range(1, 101):
        record: dict = {"id": i}

        # name -- occasionally null
        if rng.random() < 0.03:
            record["name"] = None
        else:
            record["name"] = _rand_name(rng)

        # age -- include edge values (18, 65) and occasional nulls
        if rng.random() < 0.04:
            record["age"] = None
        elif rng.random() < 0.05:
            record["age"] = rng.choice([18, 65])
        else:
            record["age"] = rng.randint(20, 62)

        # salary -- include zero and very high edge values, occasional null
        if rng.random() < 0.03:
            record["salary"] = None
        elif rng.random() < 0.02:
            record["salary"] = 0
        elif rng.random() < 0.02:
            record["salary"] = 500000
        else:
            record["salary"] = round(rng.gauss(75000, 20000), 2)

        # department
        if rng.random() < 0.02:
            record["department"] = None
        else:
            record["department"] = rng.choice(departments)

        records.append(record)

    path = OUTPUT_DIR / "simple_data.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    print(f"Wrote {path}  ({len(records)} records)")


# ── messy_data.csv ──────────────────────────────────────────────────

def generate_messy_data() -> None:
    rng = random.Random(SEED)
    departments_canonical = ["Engineering", "Sales", "Marketing", "HR", "Finance"]

    def _random_date(rng: random.Random) -> str:
        y = rng.randint(2020, 2025)
        m = rng.randint(1, 12)
        d = rng.randint(1, 28)
        fmt = rng.choice(["iso", "dmy", "mdy"])
        if fmt == "iso":
            return f"{y}-{m:02d}-{d:02d}"
        elif fmt == "dmy":
            return f"{d:02d}/{m:02d}/{y}"
        else:
            return f"{m:02d}-{d:02d}-{y}"

    def _casing_variant(name: str, rng: random.Random) -> str:
        r = rng.random()
        if r < 0.33:
            return name
        elif r < 0.66:
            return name.lower()
        else:
            return name.upper()

    missing_sentinels = ["", "N/A", "null", "-", "None"]

    fieldnames = ["id", "name", "email", "department", "join_date", "salary"]
    rows = []

    for i in range(1, 191):  # 190 unique rows; 10 will be duplicated
        row: dict = {"id": str(i)}

        # name -- occasional whitespace issues
        name = _rand_name(rng)
        if rng.random() < 0.08:
            name = "  " + name + " "
        if rng.random() < 0.05:
            name = rng.choice(missing_sentinels)
        row["name"] = name

        # email
        if rng.random() < 0.06:
            row["email"] = rng.choice(missing_sentinels)
        else:
            row["email"] = name.strip().lower().replace(" ", ".") + "@example.com" if name.strip() and name not in missing_sentinels else "unknown@example.com"

        # department with inconsistent casing
        if rng.random() < 0.05:
            row["department"] = rng.choice(missing_sentinels)
        else:
            row["department"] = _casing_variant(rng.choice(departments_canonical), rng)

        # join_date with mixed formats
        if rng.random() < 0.04:
            row["join_date"] = rng.choice(missing_sentinels)
        else:
            row["join_date"] = _random_date(rng)

        # salary
        if rng.random() < 0.06:
            row["salary"] = rng.choice(missing_sentinels)
        else:
            row["salary"] = str(round(rng.gauss(72000, 18000), 2))

        rows.append(row)

    # Pick 10 rows to duplicate (exact copies)
    duplicate_indices = rng.sample(range(len(rows)), 10)
    for idx in duplicate_indices:
        rows.append(dict(rows[idx]))

    rng.shuffle(rows)

    path = OUTPUT_DIR / "messy_data.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {path}  ({len(rows)} rows including duplicates)")


# ── multi-table relational data ─────────────────────────────────────

def generate_multi_table_data() -> None:
    rng = random.Random(SEED)

    # Products (20)
    categories = ["Electronics", "Clothing", "Home", "Books", "Sports"]
    product_names = [
        "Widget A", "Widget B", "Gadget Pro", "Gadget Lite", "Comfort Tee",
        "Warm Jacket", "Cozy Blanket", "Desk Lamp", "Bookshelf", "Novel X",
        "Novel Y", "Textbook Z", "Running Shoes", "Yoga Mat", "Tennis Racket",
        "Headphones", "Keyboard", "Monitor Stand", "Throw Pillow", "Water Bottle",
    ]
    products = []
    for pid in range(1, 21):
        products.append({
            "id": pid,
            "name": product_names[pid - 1],
            "category": rng.choice(categories),
            "price": round(rng.uniform(9.99, 299.99), 2),
        })

    path = OUTPUT_DIR / "multi_table_products.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "category", "price"])
        w.writeheader()
        w.writerows(products)
    print(f"Wrote {path}  ({len(products)} products)")

    # Customers (50)
    regions = ["North", "South", "East", "West"]
    customers = []
    for cid in range(1, 51):
        name = _rand_name(rng)
        customers.append({
            "id": cid,
            "name": name,
            "email": name.lower().replace(" ", ".") + "@example.com",
            "region": rng.choice(regions),
        })

    path = OUTPUT_DIR / "multi_table_customers.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "email", "region"])
        w.writeheader()
        w.writerows(customers)
    print(f"Wrote {path}  ({len(customers)} customers)")

    # Orders (200) -- with some interesting correlations
    # Correlation: customers in "West" tend to buy more Electronics;
    # customers in "East" tend to buy more Books.
    electronics_ids = [p["id"] for p in products if p["category"] == "Electronics"]
    books_ids = [p["id"] for p in products if p["category"] == "Books"]
    all_product_ids = [p["id"] for p in products]

    orders = []
    for oid in range(1, 201):
        cid = rng.randint(1, 50)
        cust_region = customers[cid - 1]["region"]

        # Bias product selection by region
        if cust_region == "West" and electronics_ids and rng.random() < 0.6:
            pid = rng.choice(electronics_ids)
        elif cust_region == "East" and books_ids and rng.random() < 0.5:
            pid = rng.choice(books_ids)
        else:
            pid = rng.choice(all_product_ids)

        product_price = products[pid - 1]["price"]
        quantity = rng.randint(1, 5)
        amount = round(product_price * quantity, 2)

        year = rng.choice([2024, 2025])
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        date_str = f"{year}-{month:02d}-{day:02d}"

        orders.append({
            "id": oid,
            "customer_id": cid,
            "product_id": pid,
            "amount": amount,
            "date": date_str,
        })

    path = OUTPUT_DIR / "multi_table_orders.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "customer_id", "product_id", "amount", "date"])
        w.writeheader()
        w.writerows(orders)
    print(f"Wrote {path}  ({len(orders)} orders)")


# ── main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    generate_simple_data()
    generate_messy_data()
    generate_multi_table_data()
    print("\nAll fixture files generated successfully.")
