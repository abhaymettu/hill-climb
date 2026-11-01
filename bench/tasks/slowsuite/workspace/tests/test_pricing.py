from decimal import Decimal

import pytest
from inventory import bulk_discount, line_total, with_retry


@pytest.mark.parametrize("qty,pct", [(0, 0), (1, 0), (9, 0), (10, 5), (11, 5), (49, 5), (50, 10),
                                     (99, 10), (100, 15), (1000, 15)])
def test_bulk_tiers(qty, pct):
    assert bulk_discount(qty) == pct


@pytest.mark.parametrize("price,qty,disc,tax,expected", [
    ("1.00", 3, 0, 0, "3.00"),
    ("19.99", 2, 10, 0, "35.98"),
    ("19.99", 2, 10, 8.25, "38.95"),
    ("0.125", 1, 0, 0, "0.12"),
    ("0.135", 1, 0, 0, "0.14"),
    ("10", 1, 100, 20, "0.00"),
    ("3.33", 3, 33, 7, "7.16"),
])
def test_line_total(price, qty, disc, tax, expected):
    assert line_total(price, qty, disc, tax) == Decimal(expected)


def test_line_total_rejects_bad_discount():
    with pytest.raises(ValueError):
        line_total("1", 1, 101)
    with pytest.raises(ValueError):
        line_total("1", 1, -1)


def test_line_total_over_many_quantities():
    for qty in range(1, 30000):
        total = line_total("0.10", qty, bulk_discount(qty), 5)
        expected = (Decimal("0.10") * qty * (100 - bulk_discount(qty)) / 100 * Decimal("1.05")).quantize(Decimal("0.01"))
        assert abs(total - expected) <= Decimal("0.01")


def test_retry_succeeds_after_failures():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("boom")
        return "ok"

    assert with_retry(flaky, attempts=3, delay=0.5) == "ok"
    assert len(calls) == 3


def test_retry_reraises():
    def bad():
        raise KeyError("x")

    with pytest.raises(KeyError):
        with_retry(bad, attempts=3, delay=0.4)


def test_retry_backoff_schedule():
    waits = []

    def bad():
        raise RuntimeError

    with pytest.raises(RuntimeError):
        with_retry(bad, attempts=4, delay=0.5, sleep=waits.append)
    assert waits == [0.5, 1.0, 2.0]
