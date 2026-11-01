"""A small inventory and pricing library."""
import json
import time
from decimal import ROUND_HALF_EVEN, Decimal


class OutOfStock(Exception):
    pass


class Catalog:
    def __init__(self):
        self.items = {}

    def add(self, sku, price, qty=0, tags=()):
        if sku in self.items:
            raise ValueError(f"duplicate sku {sku}")
        if Decimal(str(price)) < 0:
            raise ValueError("negative price")
        self.items[sku] = {"price": Decimal(str(price)), "qty": int(qty), "tags": set(tags)}

    def restock(self, sku, qty):
        if qty <= 0:
            raise ValueError("restock must be positive")
        self.items[sku]["qty"] += qty

    def take(self, sku, qty):
        item = self.items[sku]
        if item["qty"] < qty:
            raise OutOfStock(sku)
        item["qty"] -= qty
        return item["qty"]

    def tagged(self, tag):
        return sorted(sku for sku, it in self.items.items() if tag in it["tags"])

    def value(self):
        return sum((it["price"] * it["qty"] for it in self.items.values()), Decimal("0"))

    def to_json(self):
        return json.dumps({s: {"price": str(i["price"]), "qty": i["qty"], "tags": sorted(i["tags"])}
                           for s, i in sorted(self.items.items())})

    @classmethod
    def from_json(cls, text):
        c = cls()
        for sku, it in json.loads(text).items():
            c.add(sku, it["price"], it["qty"], it["tags"])
        return c


def line_total(price, qty, discount_pct=0, tax_pct=0):
    """Price for qty units with a percentage discount, then tax, rounded half-even to cents."""
    if not 0 <= discount_pct <= 100:
        raise ValueError("discount out of range")
    gross = Decimal(str(price)) * qty
    net = gross * (Decimal(100) - Decimal(str(discount_pct))) / Decimal(100)
    taxed = net * (Decimal(100) + Decimal(str(tax_pct))) / Decimal(100)
    return taxed.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def bulk_discount(qty):
    """Percent off by quantity tier: 10+ is 5, 50+ is 10, 100+ is 15."""
    if qty >= 100:
        return 15
    if qty >= 50:
        return 10
    if qty >= 10:
        return 5
    return 0


def with_retry(fn, attempts=3, delay=0.5, sleep=time.sleep):
    """Call fn until it succeeds, sleeping delay * 2**i between failures; re-raise the last error."""
    for i in range(attempts):
        try:
            return fn()
        except Exception:
            if i == attempts - 1:
                raise
            sleep(delay * 2 ** i)
