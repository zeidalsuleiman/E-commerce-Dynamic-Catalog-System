"""Build filtered product queries from user-selected attribute filters.

One EXISTS clause per active filter. Always narrows by category first,
so the candidate set is small before attribute work begins.
"""
from app.db import query

VALUE_TABLE = {
    "int": ("product_value_int", "value"),
    "decimal": ("product_value_decimal", "value"),
    "varchar": ("product_value_varchar", "value"),
    "datetime": ("product_value_datetime", "value"),
    "option": ("product_value_option", "option_id"),
    "multi_option": ("product_value_multi_option", "option_id"),
}


def parse_filters(params, attributes):
    """Turn query params into a list of filter specs.

    Recognised param shapes:
      ?make=6          -> option equality (repeatable for OR)
      ?year_min=2018   -> range lower bound
      ?year_max=2022   -> range upper bound
    """
    by_code = {a["code"]: a for a in attributes if a["is_filterable"]}
    filters = []

    for code, attr in by_code.items():
        if attr["data_type"] in ("option", "multi_option"):
            values = params.getlist(code)
            values = [int(v) for v in values if v]
            if values:
                filters.append({"attr": attr, "op": "in", "values": values})
        else:
            lo = params.get(f"{code}_min")
            hi = params.get(f"{code}_max")
            if lo not in (None, "") or hi not in (None, ""):
                filters.append({
                    "attr": attr, "op": "range",
                    "min": lo or None, "max": hi or None,
                })
    return filters


def build_where(filters):
    """Return (sql_fragments, params) — one EXISTS clause per filter."""
    clauses, params = [], []

    for f in filters:
        attr = f["attr"]
        table, column = VALUE_TABLE[attr["data_type"]]
        attr_id = attr["attribute_id"]

        if f["op"] == "in":
            placeholders = ", ".join(["%s"] * len(f["values"]))
            clauses.append(
                f"EXISTS (SELECT 1 FROM {table} v "
                f"WHERE v.product_id = p.id AND v.attribute_id = %s "
                f"AND v.{column} IN ({placeholders}))"
            )
            params.extend([attr_id, *f["values"]])

        else:
            conds = []
            sub_params = [attr_id]
            if f["min"] is not None:
                conds.append(f"v.{column} >= %s")
                sub_params.append(f["min"])
            if f["max"] is not None:
                conds.append(f"v.{column} <= %s")
                sub_params.append(f["max"])
            clauses.append(
                f"EXISTS (SELECT 1 FROM {table} v "
                f"WHERE v.product_id = p.id AND v.attribute_id = %s "
                f"AND {' AND '.join(conds)})"
            )
            params.extend(sub_params)

    return clauses, params


def search_products(category_id, filters, limit=24, offset=0):
    """Products in a category matching all active filters."""
    clauses, params = build_where(filters)
    where = " AND ".join(["p.primary_category_id = %s", "p.status = 'active'"]
                         + clauses)

    sql = (
        "SELECT p.id, p.title, p.price "
        "FROM product p "
        f"WHERE {where} "
        "ORDER BY p.created_at DESC "
        "LIMIT %s OFFSET %s"
    )
    return query(sql, [category_id, *params, limit, offset])


def facet_counts(category_id, filters, attribute):
    """Option counts for one attribute, within the current result set.

    The attribute's own filter is excluded, so selecting Mercedes doesn't
    make every other make show zero.
    """
    others = [f for f in filters if f["attr"]["code"] != attribute["code"]]
    clauses, params = build_where(others)
    where = " AND ".join(["p.primary_category_id = %s", "p.status = 'active'"]
                         + clauses)

    table, column = VALUE_TABLE[attribute["data_type"]]
    sql = (
        f"SELECT v.{column} AS option_id, COUNT(*) AS n "
        f"FROM {table} v "
        "JOIN product p ON p.id = v.product_id "
        f"WHERE v.attribute_id = %s AND {where} "
        f"GROUP BY v.{column}"
    )
    rows = query(sql, [attribute["attribute_id"], category_id, *params])
    return {r["option_id"]: r["n"] for r in rows}