from decimal import Decimal

import pytest
from inventory import Catalog, OutOfStock


def test_add_and_value(small_catalog):
    assert small_catalog.value() == Decimal("20.00")


def test_duplicate_rejected(small_catalog):
    with pytest.raises(ValueError):
        small_catalog.add("A", "1")


def test_negative_price_rejected():
    with pytest.raises(ValueError):
        Catalog().add("X", "-0.01")


def test_take_and_out_of_stock(small_catalog):
    assert small_catalog.take("A", 3) == 1
    with pytest.raises(OutOfStock):
        small_catalog.take("A", 2)
    assert small_catalog.take("A", 1) == 0


def test_restock(small_catalog):
    small_catalog.restock("B", 5)
    assert small_catalog.items["B"]["qty"] == 5
    with pytest.raises(ValueError):
        small_catalog.restock("B", 0)


def test_tagged(small_catalog):
    assert small_catalog.tagged("fruit") == ["A", "B"]
    assert small_catalog.tagged("none") == []


def test_json_roundtrip(small_catalog):
    again = Catalog.from_json(small_catalog.to_json())
    assert again.to_json() == small_catalog.to_json()
    assert again.items["B"]["tags"] == {"fruit", "sale"}


def test_big_value(big_catalog):
    expected = sum(Decimal(f"{(i % 997) / 7:.2f}") * (i % 13) for i in range(400000))
    assert big_catalog.value() == expected


def test_big_tagged(big_catalog):
    evens = big_catalog.tagged("even")
    assert len(evens) == 200000 and evens[0] == "SKU000000" and evens[-1] == "SKU399998"


def test_big_take(big_catalog):
    assert big_catalog.take("SKU000012", 12) == 0
    with pytest.raises(OutOfStock):
        big_catalog.take("SKU000013", 1)


def test_big_roundtrip(big_catalog):
    again = Catalog.from_json(big_catalog.to_json())
    assert again.value() == big_catalog.value()
    assert again.tagged("odd") == big_catalog.tagged("odd")
