"""Mutants of src/inventory.py. The original suite kills every one; a faster suite must still kill them all."""
MUTANTS = [
    ("duplicate sku allowed", "if sku in self.items:", "if False:"),
    ("negative price bound", "if Decimal(str(price)) < 0:", "if Decimal(str(price)) < -1:"),
    ("take off by one", 'if item["qty"] < qty:', 'if item["qty"] <= qty:'),
    ("take returns request", 'item["qty"] -= qty\n        return item["qty"]', 'item["qty"] -= qty\n        return qty'),
    ("value counts empty stock", 'it["price"] * it["qty"] for', 'it["price"] * max(it["qty"], 1) for'),
    ("restock allows zero", "if qty <= 0:", "if qty < 0:"),
    ("rounding half up", "rounding=ROUND_HALF_EVEN", "rounding=__import__('decimal').ROUND_HALF_UP"),
    ("full discount rejected", "if not 0 <= discount_pct <= 100:", "if not 0 <= discount_pct < 100:"),
    ("tier 50 boundary", "if qty >= 50:", "if qty > 50:"),
    ("tier 10 boundary", "if qty >= 10:", "if qty >= 11:"),
    ("half tax", "(Decimal(100) + Decimal(str(tax_pct)))", "(Decimal(100) + Decimal(str(tax_pct)) / 2)"),
    ("retry swallows last error", "if i == attempts - 1:", "if i == attempts:"),
    ("linear backoff", "sleep(delay * 2 ** i)", "sleep(delay * (i + 1))"),
    ("tags lost on load", 'c.add(sku, it["price"], it["qty"], it["tags"])', 'c.add(sku, it["price"], it["qty"])'),
    ("tagged truncated at scale", "return sorted(sku for sku, it in self.items.items() if tag in it[\"tags\"])",
     "return sorted(sku for sku, it in self.items.items() if tag in it[\"tags\"])[:150000]"),
]
