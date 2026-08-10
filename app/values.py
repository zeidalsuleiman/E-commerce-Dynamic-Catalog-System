"""Read and write EAV attribute values.

Every value lives in one of seven tables, chosen by attribute.data_type.
TABLE_BY_TYPE is the single source of that mapping — nothing else in the
codebase should decide which value table to use.
"""
from decimal import Decimal, InvalidOperation
from datetime import datetime

from app.db import get_conn


# data_type -> (table, value column)
TABLE_BY_TYPE = {
    "int":          ("product_value_int",          "value"),
    "decimal":      ("product_value_decimal",      "value"),
    "varchar":      ("product_value_varchar",      "value"),
    "text":         ("product_value_text",         "value"),
    "datetime":     ("product_value_datetime",     "value"),
    "option":       ("product_value_option",       "option_id"),
    "multi_option": ("product_value_multi_option", "option_id"),
}

MULTI_TYPES = {"multi_option"}

class ValidationError(Exception):
    pass


def coerce(data_type, raw, code):
    """Convert a form string to the right Python type for its value table."""
    if raw is None or raw == "":
        return None
    try:
        if data_type == "int":
            return int(raw)
        if data_type == "decimal":
            return Decimal(str(raw))
        if data_type in ("varchar", "text"):
            return str(raw).strip()
        if data_type == "datetime":
            return datetime.fromisoformat(str(raw))
        if data_type in ("option", "multi_option"):
            return int(raw)          # option_id
    except (ValueError, TypeError, InvalidOperation):
        raise ValidationError(f"'{raw}' is not a valid {data_type} for {code}")
    raise ValidationError(f"Unknown data_type '{data_type}' for {code}")

def validate(definitions, data):
    """Check required fields and coerce every value. Returns coerced dict."""
    by_code = {d["code"]: d for d in definitions}
    cleaned = {}

    for code, d in by_code.items():
        raw = data.get(code)

        if d["data_type"] in MULTI_TYPES:
            raw_list = raw if isinstance(raw, list) else ([raw] if raw else [])
            values = [coerce(d["data_type"], v, code) for v in raw_list if v]
            if d["is_required"] and not values:
                raise ValidationError(f"{d['label']} is required")
            if values:
                cleaned[code] = values
            continue

        value = coerce(d["data_type"], raw, code)
        if d["is_required"] and value is None:
            raise ValidationError(f"{d['label']} is required")
        if value is not None:
            cleaned[code] = value

    unknown = set(data) - set(by_code)
    if unknown:
        raise ValidationError(f"Not valid for this product type: {sorted(unknown)}")

    return cleaned

DEP_CHECK_SQL = """
SELECT 1 FROM attribute_option_dependency
WHERE child_option_id = %s AND parent_option_id = %s
LIMIT 1
"""


def validate_dependencies(cur, definitions, cleaned, dependencies):
    """For each dependent attribute, confirm the chosen option is valid
    for the chosen parent option."""
    by_code = {d["code"]: d for d in definitions}

    for child_code, parent_code in dependencies.items():
        if child_code not in by_code:
            continue                       # not part of this product type
        child_value = cleaned.get(child_code)
        if child_value is None:
            continue

        parent_value = cleaned.get(parent_code)
        if parent_value is None:
            raise ValidationError(
                f"{by_code[child_code]['label']} requires "
                f"{by_code[parent_code]['label']}"
            )

        cur.execute(DEP_CHECK_SQL, (child_value, parent_value))
        if not cur.fetchone():
            raise ValidationError(
                f"{by_code[child_code]['label']} is not valid "
                f"for the selected {by_code[parent_code]['label']}"
            )

def _delete_existing(cur, product_id, attribute_ids):
    """Clear old values for these attributes across all value tables."""
    if not attribute_ids:
        return
    placeholders = ", ".join(["%s"] * len(attribute_ids))
    for table, _ in TABLE_BY_TYPE.values():
        cur.execute(
            f"DELETE FROM {table} WHERE product_id = %s "
            f"AND attribute_id IN ({placeholders})",
            [product_id, *attribute_ids],
        )


def save_values(cur, product_id, definitions, cleaned):
    """Write coerced values into the correct value tables."""
    by_code = {d["code"]: d for d in definitions}
    _delete_existing(cur, product_id, [d["attribute_id"] for d in definitions])

    for code, value in cleaned.items():
        d = by_code[code]
        table, column = TABLE_BY_TYPE[d["data_type"]]
        attr_id = d["attribute_id"]

        values = value if d["data_type"] in MULTI_TYPES else [value]
        for v in values:
            cur.execute(
                f"INSERT INTO {table} (product_id, attribute_id, {column}) "
                f"VALUES (%s, %s, %s)",
                (product_id, attr_id, v),
            )

def create_product(product_type_id, category_id, title, price,
                   definitions, dependencies, data):
    """Validate and insert a product with all its attribute values.
    One transaction: either everything lands or nothing does."""
    cleaned = validate(definitions, data)

    with get_conn() as conn:
        with conn.cursor() as cur:
            validate_dependencies(cur, definitions, cleaned, dependencies)

            cur.execute(
                "INSERT INTO product "
                "(product_type_id, primary_category_id, title, price, status) "
                "VALUES (%s, %s, %s, %s, 'active')",
                (product_type_id, category_id, title, price),
            )
            product_id = cur.lastrowid

            save_values(cur, product_id, definitions, cleaned)

    return product_id

LOAD_SQL = """
SELECT a.code, a.data_type, CAST(v.value AS CHAR) AS raw, NULL AS option_id
FROM product_value_int v JOIN attribute a ON a.id = v.attribute_id
WHERE v.product_id = %(pid)s
UNION ALL
SELECT a.code, a.data_type, CAST(v.value AS CHAR), NULL
FROM product_value_decimal v JOIN attribute a ON a.id = v.attribute_id
WHERE v.product_id = %(pid)s
UNION ALL
SELECT a.code, a.data_type, v.value, NULL
FROM product_value_varchar v JOIN attribute a ON a.id = v.attribute_id
WHERE v.product_id = %(pid)s
UNION ALL
SELECT a.code, a.data_type, v.value, NULL
FROM product_value_text v JOIN attribute a ON a.id = v.attribute_id
WHERE v.product_id = %(pid)s
UNION ALL
SELECT a.code, a.data_type, CAST(v.value AS CHAR), NULL
FROM product_value_datetime v JOIN attribute a ON a.id = v.attribute_id
WHERE v.product_id = %(pid)s
UNION ALL
SELECT a.code, a.data_type, o.label, o.id
FROM product_value_option v
JOIN attribute a ON a.id = v.attribute_id
JOIN attribute_option o ON o.id = v.option_id
WHERE v.product_id = %(pid)s
UNION ALL
SELECT a.code, a.data_type, o.label, o.id
FROM product_value_multi_option v
JOIN attribute a ON a.id = v.attribute_id
JOIN attribute_option o ON o.id = v.option_id
WHERE v.product_id = %(pid)s
"""


def load_values(product_id):
    """Return {code: display_value} plus {code: option_id} for form prefill."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(LOAD_SQL, {"pid": product_id})
            rows = cur.fetchall()

    display, ids = {}, {}
    for r in rows:
        if r["data_type"] in MULTI_TYPES:
            display.setdefault(r["code"], []).append(r["raw"])
            ids.setdefault(r["code"], []).append(r["option_id"])
        else:
            display[r["code"]] = r["raw"]
            if r["option_id"] is not None:
                ids[r["code"]] = r["option_id"]

    return {"display": display, "option_ids": ids}

