"""
Unit tests for app/resolver.py's get_type_chain().

get_type_chain() takes a cursor and runs one recursive CTE, so we can
test its logic (ordering, unknown-type handling, cycle detection)
against a fake cursor that returns canned rows — no real DB needed.
"""
import pytest

from app.resolver import get_type_chain


class FakeCursor:
    """Returns canned rows regardless of the query, for unit-testing
    functions that only care about what fetchall() returns."""

    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self._rows


class TestGetTypeChain:
    def test_single_type_no_parent(self):
        # PRODUCT with no ancestors: depth 0 only
        cur = FakeCursor([{"id": 1, "depth": 0}])
        assert get_type_chain(cur, 1) == [1]

    def test_chain_ordered_root_first(self):
        # CAR -> VEHICLE -> PRODUCT, returned root-first (deepest depth first)
        cur = FakeCursor([
            {"id": 1, "depth": 2},   # PRODUCT (root), depth 2 from CAR's perspective
            {"id": 2, "depth": 1},   # VEHICLE
            {"id": 3, "depth": 0},   # CAR (the type we asked about)
        ])
        assert get_type_chain(cur, 3) == [1, 2, 3]

    def test_unknown_type_raises(self):
        cur = FakeCursor([])
        with pytest.raises(ValueError, match="Unknown product_type_id"):
            get_type_chain(cur, 999)

    def test_cycle_raises(self):
        # Same id appearing twice indicates the recursive CTE looped
        cur = FakeCursor([
            {"id": 1, "depth": 0},
            {"id": 2, "depth": 1},
            {"id": 1, "depth": 2},   # cycle back to id 1
        ])
        with pytest.raises(ValueError, match="Cycle"):
            get_type_chain(cur, 1)
