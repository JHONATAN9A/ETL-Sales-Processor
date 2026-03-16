import csv
import random
from datetime import date, timedelta

ROWS = 1_000
OUTPUT = "test_large_2.csv"

start_date = date(2026, 1, 1)
product_ids = list(range(1001, 1101))  # 100 productos

with open(OUTPUT, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["date", "product_id", "quantity", "price"])

    for _ in range(ROWS):
        row_date = start_date + timedelta(days=random.randint(0, 364))
        product_id = random.choice(product_ids)
        quantity = random.randint(1, 50)
        price = round(random.uniform(1.0, 500.0), 2)
        writer.writerow([row_date, product_id, quantity, price])

print(f"Generado {OUTPUT} con {ROWS:,} filas")
