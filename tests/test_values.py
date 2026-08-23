"""
Unit tests for app/values.py — coerce, validate, apply_rules.

These three functions are pure (no DB access), so these tests run fast
and need no MySQL connection. Tests that DO need the DB (save_values,
create_product, etc.) belong in a separate integration test module and
are intentionally not included here.
"""
import pytest
from decimal import Decimal

from app.values import coerce, validate, apply_rules, ValidationError


# ---------- coerce ----------

class TestCoerce:
    def test_int_valid(self):
        assert coerce("int", "42", "mileage") == 42

    def test_int_invalid_raises(self):
        with pytest.raises(ValidationError):
            coerce("int", "not-a-number", "mileage")

    def test_decimal_valid(self):
        assert coerce("decimal", "19.99", "price") == Decimal("19.99")

    def test_decimal_invalid_raises(self):
        with pytest.raises(ValidationError):
            coerce("decimal", "abc", "price")

    def test_varchar_strips_whitespace(self):
        assert coerce("varchar", "  Mercedes  ", "make") == "Mercedes"

    def test_text_passthrough(self):
        assert coerce("text", "a long description", "description") == \
            "a long description"

    def test_datetime_valid_iso(self):
        result = coerce("datetime", "2026-08-23T10:00:00", "created_at")
        assert result.year == 2026 and result.month == 8 and result.day == 23

    def test_datetime_invalid_raises(self):
        with pytest.raises(ValidationError):
            coerce("datetime", "not-a-date", "created_at")

    def test_option_valid(self):
        assert coerce("option", "7", "make") == 7

    def test_option_invalid_raises(self):
        with pytest.raises(ValidationError):
            coerce("option", "seven", "make")

    def test_none_or_empty_returns_none(self):
        assert coerce("int", None, "mileage") is None
        assert coerce("int", "", "mileage") is None

    def test_unknown_data_type_raises(self):
        with pytest.raises(ValidationError):
            coerce("nonsense_type", "42", "mileage")


# ---------- validate ----------

def make_def(code, data_type, required=False, label=None):
    return {
        "code": code,
        "data_type": data_type,
        "is_required": required,
        "label": label or code.title(),
        "attribute_id": hash(code) % 1000,  # not used by validate() itself
    }


class TestValidate:
    def test_required_field_missing_raises(self):
        defs = [make_def("mileage", "int", required=True)]
        with pytest.raises(ValidationError, match="required"):
            validate(defs, {})

    def test_required_field_present_passes(self):
        defs = [make_def("mileage", "int", required=True)]
        result = validate(defs, {"mileage": "50000"})
        assert result == {"mileage": 50000}

    def test_optional_field_omitted_is_fine(self):
        defs = [make_def("mileage", "int", required=False)]
        result = validate(defs, {})
        assert result == {}

    def test_unknown_field_raises(self):
        defs = [make_def("mileage", "int")]
        with pytest.raises(ValidationError, match="Not valid"):
            validate(defs, {"turbo_boost": "9000"})

    def test_multi_option_collects_list(self):
        defs = [make_def("features", "multi_option")]
        result = validate(defs, {"features": ["1", "2", "3"]})
        assert result == {"features": [1, 2, 3]}

    def test_multi_option_required_empty_raises(self):
        defs = [make_def("features", "multi_option", required=True)]
        with pytest.raises(ValidationError, match="required"):
            validate(defs, {"features": []})

    def test_multi_option_single_value_wrapped_in_list(self):
        defs = [make_def("features", "multi_option")]
        result = validate(defs, {"features": "5"})
        assert result == {"features": [5]}


# ---------- apply_rules ----------

class TestApplyRules:
    def test_force_value_fills_missing_target(self):
        defs = [make_def("city", "varchar"), make_def("condition", "option")]
        cleaned = {"condition": 1}  # e.g. "new"
        rules = {
            "condition": {
                1: [{
                    "rule_type": "force_value",
                    "rule_value": "Amman",
                    "message": None,
                    "target_code": "city",
                    "target_data_type": "varchar",
                }]
            }
        }
        result = apply_rules(defs, cleaned, rules)
        assert result["city"] == "Amman"

    def test_force_value_conflict_raises(self):
        defs = [make_def("city", "varchar"), make_def("condition", "option")]
        cleaned = {"condition": 1, "city": "Irbid"}
        rules = {
            "condition": {
                1: [{
                    "rule_type": "force_value",
                    "rule_value": "Amman",
                    "message": None,
                    "target_code": "city",
                    "target_data_type": "varchar",
                }]
            }
        }
        with pytest.raises(ValidationError):
            apply_rules(defs, cleaned, rules)

    def test_hide_removes_target(self):
        defs = [make_def("warranty_months", "int"), make_def("condition", "option")]
        cleaned = {"condition": 2, "warranty_months": 12}
        rules = {
            "condition": {
                2: [{
                    "rule_type": "hide",
                    "rule_value": None,
                    "message": None,
                    "target_code": "warranty_months",
                    "target_data_type": "int",
                }]
            }
        }
        result = apply_rules(defs, cleaned, rules)
        assert "warranty_months" not in result

    def test_require_missing_raises(self):
        defs = [make_def("warranty_months", "int"), make_def("condition", "option")]
        cleaned = {"condition": 1}
        rules = {
            "condition": {
                1: [{
                    "rule_type": "require",
                    "rule_value": None,
                    "message": None,
                    "target_code": "warranty_months",
                    "target_data_type": "int",
                }]
            }
        }
        with pytest.raises(ValidationError):
            apply_rules(defs, cleaned, rules)

    def test_max_over_limit_raises(self):
        defs = [make_def("mileage", "int"), make_def("condition", "option")]
        cleaned = {"condition": 1, "mileage": 500000}
        rules = {
            "condition": {
                1: [{
                    "rule_type": "max",
                    "rule_value": "300000",
                    "message": None,
                    "target_code": "mileage",
                    "target_data_type": "int",
                }]
            }
        }
        with pytest.raises(ValidationError):
            apply_rules(defs, cleaned, rules)

    def test_min_under_limit_raises(self):
        defs = [make_def("year", "int"), make_def("condition", "option")]
        cleaned = {"condition": 1, "year": 1990}
        rules = {
            "condition": {
                1: [{
                    "rule_type": "min",
                    "rule_value": "2000",
                    "message": None,
                    "target_code": "year",
                    "target_data_type": "int",
                }]
            }
        }
        with pytest.raises(ValidationError):
            apply_rules(defs, cleaned, rules)

    def test_no_trigger_selected_no_rules_fire(self):
        defs = [make_def("mileage", "int"), make_def("condition", "option")]
        cleaned = {"mileage": 50000}  # condition not selected
        rules = {
            "condition": {
                1: [{
                    "rule_type": "max",
                    "rule_value": "10",
                    "message": None,
                    "target_code": "mileage",
                    "target_data_type": "int",
                }]
            }
        }
        result = apply_rules(defs, cleaned, rules)
        assert result["mileage"] == 50000  # untouched
