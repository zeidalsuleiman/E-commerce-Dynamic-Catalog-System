"""Resolve the effective attribute set for a product type.

Walks the product_type inheritance chain and merges attribute bindings,
root-first, so a child type's binding overrides its parent's.
"""
from app.db import get_conn


CHAIN_SQL = """
WITH RECURSIVE chain AS (
    SELECT id, parent_type_id, 0 AS depth
    FROM product_type
    WHERE id = %s
    UNION ALL
    SELECT pt.id, pt.parent_type_id, c.depth + 1
    FROM product_type pt
    JOIN chain c ON pt.id = c.parent_type_id
)
SELECT id, depth FROM chain ORDER BY depth DESC
"""

BINDINGS_SQL = """
SELECT
    a.id            AS attribute_id,
    a.code,
    a.label,
    a.data_type,
    a.input_type,
    a.unit,
    a.is_filterable,
    pta.product_type_id,
    pta.is_required,
    pta.group_name,
    pta.sort_order
FROM product_type_attribute pta
JOIN attribute a ON a.id = pta.attribute_id
WHERE pta.product_type_id IN ({placeholders})
"""

DEPENDENCY_SQL = """
SELECT
    child.code  AS child_code,
    parent.code AS parent_code
FROM attribute_dependency d
JOIN attribute child  ON child.id  = d.child_attribute_id
JOIN attribute parent ON parent.id = d.parent_attribute_id
"""

def get_type_chain(cur, product_type_id):
    cur.execute(CHAIN_SQL, (product_type_id,))
    rows = cur.fetchall()
    if not rows:
        raise ValueError(f"Unknown product_type_id: {product_type_id}")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Cycle in product_type hierarchy from {product_type_id}")
    return ids

def resolve(product_type_id):
    """Return {'attributes': [...], 'dependencies': {child_code: parent_code}}.

    Attributes are merged root-first, so the most specific type wins.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            chain = get_type_chain(cur, product_type_id)

            placeholders = ", ".join(["%s"] * len(chain))
            cur.execute(BINDINGS_SQL.format(placeholders=placeholders), chain)
            rows = cur.fetchall()

            by_type = {}
            for r in rows:
                by_type.setdefault(r["product_type_id"], []).append(r)

            merged = {}
            for type_id in chain:                    # root -> leaf
                for r in by_type.get(type_id, []):
                    merged[r["code"]] = dict(r)      # later write wins

            attributes = sorted(
                merged.values(),
                key=lambda a: (a["group_name"] or "", a["sort_order"]),
            )

            deps = get_dependencies(cur)

    return {"attributes": attributes, "dependencies": deps}

DEPENDENCY_SQL = """
SELECT DISTINCT
    ca.code AS child_code,
    pa.code AS parent_code
FROM attribute_option_dependency d
JOIN attribute_option co ON co.id = d.child_option_id
JOIN attribute_option po ON po.id = d.parent_option_id
JOIN attribute ca ON ca.id = co.attribute_id
JOIN attribute pa ON pa.id = po.attribute_id
"""

def get_dependencies(cur):
    """Return {child_attr_code: parent_attr_code}, e.g. {'model': 'make'}."""
    cur.execute(DEPENDENCY_SQL)
    return {r["child_code"]: r["parent_code"] for r in cur.fetchall()}