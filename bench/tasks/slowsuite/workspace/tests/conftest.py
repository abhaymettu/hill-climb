import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from inventory import Catalog  # noqa: E402


def build_big_catalog():
    c = Catalog()
    for i in range(400000):
        c.add(f"SKU{i:06d}", f"{(i % 997) / 7:.2f}", i % 13, tags=("even",) if i % 2 == 0 else ("odd",))
    return c


@pytest.fixture
def big_catalog():
    return build_big_catalog()


@pytest.fixture
def small_catalog():
    c = Catalog()
    c.add("A", "2.50", 4, tags=("fruit",))
    c.add("B", "0.99", 0, tags=("fruit", "sale"))
    c.add("C", "10", 1, tags=("tool",))
    return c
